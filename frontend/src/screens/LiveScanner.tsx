import React, { useCallback, useRef, useState } from 'react';
import { Alert, Image, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { CameraView, CameraType, useCameraPermissions } from 'expo-camera';
import * as MediaLibrary from 'expo-media-library';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';

import { api } from '../lib/api';
import { isSamplePrice, scanChoices, toScanMatch } from '../lib/scan';
import type { BookFormat, GradeScanResult, ScanIdentification, ScanPhotos } from '../types';
import { Button, GradeBadge, LoadingDots, Pill, colors, usd } from '../components/ui';

type Props = { navigation: NativeStackNavigationProp<any> };
type Phase = 'capture' | 'grading' | 'review' | 'saving';
type Role = keyof ScanPhotos;

const STEPS: { role: Role; label: string; hint: string }[] = [
  { role: 'front', label: 'Front', hint: 'Center the front cover in the frame' },
  { role: 'back', label: 'Back', hint: 'Flip the book and frame the back cover' },
  { role: 'spine', label: 'Spine', hint: 'Turn the book so the spine faces the camera' },
];

const FORMAT_LABELS: Record<BookFormat, string> = {
  single_issue: 'Issue',
  annual: 'Annual',
  collected_edition: 'Collected',
  other: 'Other',
};

const describe = (b: ScanIdentification) =>
  `${b.title} #${b.issue_number}${b.format && b.format !== 'single_issue' ? ` (${FORMAT_LABELS[b.format]})` : ''}`;

type ManualBook = { title: string; issue_number: string; publisher: string; year: string; format: BookFormat };
const EMPTY_MANUAL: ManualBook = { title: '', issue_number: '', publisher: '', year: '', format: 'single_issue' };

/**
 * Live camera scan (used when demo mode is off). Guides the user through three
 * photos (front, back, spine; back and spine can be skipped), sends them to
 * POST /vision/grade, asks the user to confirm which book it is (or type it in),
 * then saves the book with its grade report.
 */
export default function LiveScanner({ navigation }: Props) {
  const [permission, requestPermission] = useCameraPermissions();
  const [libraryPermission] = MediaLibrary.usePermissions();
  const [facing, setFacing] = useState<CameraType>('back');
  const [phase, setPhase] = useState<Phase>('capture');
  const [step, setStep] = useState(0);
  const [photos, setPhotos] = useState<Partial<ScanPhotos>>({});
  const [result, setResult] = useState<GradeScanResult | null>(null);
  // Index into the choices, or 'manual' when the user typed the book in.
  const [choice, setChoice] = useState<number | 'manual'>(0);
  const [manual, setManual] = useState<ManualBook>(EMPTY_MANUAL);
  const [manualBook, setManualBook] = useState<ScanIdentification | null>(null);
  const [value, setValue] = useState<{ amount: number | null; source: string | null; loading: boolean }>({
    amount: null,
    source: null,
    loading: false,
  });
  const cameraRef = useRef<CameraView>(null);

  const reset = useCallback(() => {
    setPhotos({});
    setStep(0);
    setResult(null);
    setChoice(0);
    setManual(EMPTY_MANUAL);
    setManualBook(null);
    setPhase('capture');
  }, []);

  const reprice = useCallback(async (book: ScanIdentification, grade: number) => {
    setValue({ amount: null, source: null, loading: true });
    try {
      const est = await api.estimateValue(book.title, book.issue_number, grade);
      setValue({ amount: est.value, source: est.source, loading: false });
    } catch {
      setValue({ amount: null, source: null, loading: false }); // save without a value
    }
  }, []);

  const grade = useCallback(async (taken: Partial<ScanPhotos>) => {
    if (!taken.front) return;
    setPhase('grading');
    try {
      const graded = await api.gradeScan({ front: taken.front, back: taken.back, spine: taken.spine });
      setResult(graded);
      setChoice(0);
      setValue({ amount: graded.estimated_value ?? null, source: graded.value_source ?? null, loading: false });
      setPhase('review');
    } catch (err: any) {
      setPhase('capture');
      Alert.alert('Grading failed', err?.message ?? 'Unknown error');
    }
  }, []);

  const advance = useCallback(
    (taken: Partial<ScanPhotos>) => {
      if (step < STEPS.length - 1) setStep(step + 1);
      else grade(taken);
    },
    [grade, step],
  );

  const onCapture = useCallback(async () => {
    if (!cameraRef.current || phase !== 'capture') return;
    try {
      // Quality 0.7 keeps each photo well under the 5 MB the grader accepts.
      const photo = await cameraRef.current.takePictureAsync({ quality: 0.7, imageType: 'jpg', exif: false });
      if (!photo) throw new Error('The camera did not return a photo');
      if (Platform.OS !== 'web' && libraryPermission?.granted) {
        MediaLibrary.saveToLibraryAsync(photo.uri).catch(() => undefined); // best effort
      }
      const taken = { ...photos, [STEPS[step].role]: photo.uri };
      setPhotos(taken);
      advance(taken);
    } catch (err: any) {
      Alert.alert('Capture failed', err?.message ?? 'Unknown error');
    }
  }, [advance, libraryPermission, phase, photos, step]);

  const choices = result ? scanChoices(result) : [];
  const chosen: ScanIdentification | null =
    choice === 'manual' ? manualBook : (choices[choice] ?? null);

  const pick = (i: number) => {
    if (!result || i === choice) return;
    setChoice(i);
    if (i === 0) {
      setValue({ amount: result.estimated_value ?? null, source: result.value_source ?? null, loading: false });
    } else {
      reprice(choices[i], result.report.grade);
    }
  };

  const useManual = () => {
    if (!result) return;
    const year = parseInt(manual.year, 10);
    const book: ScanIdentification = {
      title: manual.title.trim(),
      issue_number: manual.issue_number.trim().replace(/^#/, ''),
      publisher: manual.publisher.trim() || 'Unknown',
      year: Number.isFinite(year) ? year : null,
      format: manual.format,
      key_note: null,
      signature_detected: false,
      notes: 'Entered by hand',
    };
    setManualBook(book);
    setChoice('manual');
    reprice(book, result.report.grade);
  };

  const save = useCallback(async () => {
    if (!result || !chosen) return;
    setPhase('saving');
    try {
      const comic = await api.saveScan(toScanMatch(result, chosen, value.amount), photos.front);
      reset();
      navigation.navigate('ComicDetail', { comicId: comic.id });
    } catch (err: any) {
      setPhase('review');
      Alert.alert('Could not save', err?.message ?? 'Unknown error');
    }
  }, [chosen, navigation, photos.front, reset, result, value.amount]);

  if (!permission?.granted) {
    return (
      <View className="flex-1 items-center justify-center bg-ink-950 px-6">
        <Text className="text-pop-yellow text-2xl font-bold">Camera access needed</Text>
        <Text className="text-neutral-400 mt-2 text-center">
          ComicGrade AI uses the camera to photograph the front, back and spine of each book.
        </Text>
        <View className="mt-6">
          <Button label="Grant camera access" onPress={() => requestPermission()} />
        </View>
      </View>
    );
  }

  if ((phase === 'review' || phase === 'saving') && result) {
    const { report } = result;
    const manualReady = manual.title.trim() !== '' && manual.issue_number.trim() !== '';
    return (
      <ScrollView className="flex-1 bg-ink-950" contentContainerStyle={{ padding: 20, paddingTop: 56, paddingBottom: 40 }}>
        <Text className="text-white text-4xl font-display uppercase">Is this your book?</Text>
        <View className="flex-row gap-3 mt-4">
          {photos.front ? (
            <Image source={{ uri: photos.front }} style={{ width: 96, height: 144, borderRadius: 12 }} />
          ) : null}
          <View className="flex-1">
            <View className="flex-row items-center gap-2">
              <GradeBadge grade={report.grade} />
              <Text className="text-neutral-300">
                Likely {report.grade_low} to {report.grade_high}
              </Text>
            </View>
            <Text className="text-neutral-400 mt-2">
              Raw value {value.loading ? '…' : usd(value.amount)}
            </Text>
            {!value.loading && isSamplePrice(value.source) ? (
              <Text className="text-neutral-500 text-xs mt-1">
                Sample estimate: real raw sales prices are not connected yet.
              </Text>
            ) : null}
          </View>
        </View>

        {/* Pick the identification */}
        <View className="mt-5 gap-2">
          {choices.map((book, i) => {
            const selected = choice === i;
            return (
              <Pressable
                key={`${book.title}-${book.issue_number}-${book.format}-${i}`}
                accessibilityRole="radio"
                accessibilityState={{ selected }}
                onPress={() => pick(i)}
                className="rounded-2xl border px-4 py-3"
                style={{ borderColor: selected ? colors.yellow : colors.ink800, backgroundColor: colors.ink900 }}
              >
                <Text className="font-bold" style={{ color: selected ? colors.yellow : '#f5f5fa' }}>
                  {describe(book)}
                </Text>
                <Text className="text-neutral-400 text-xs mt-0.5">
                  {book.publisher}
                  {book.year ? ` · ${book.year}` : ''}
                  {i === 0 ? ` · best match, ${Math.round(result.match_confidence * 100)}% sure` : ''}
                </Text>
                {book.key_note ? <Text className="text-pop-cyan text-xs mt-1">{book.key_note}</Text> : null}
              </Pressable>
            );
          })}

          {/* Not listed: type it in */}
          <View
            className="rounded-2xl border px-4 py-3"
            style={{ borderColor: choice === 'manual' ? colors.yellow : colors.ink800, backgroundColor: colors.ink900 }}
          >
            <Text className="font-bold text-white">
              {choice === 'manual' && manualBook ? `Using: ${describe(manualBook)}` : 'Not listed? Enter it'}
            </Text>
            <View className="flex-row gap-2 mt-2">
              <Field placeholder="Series" value={manual.title} onChange={(t) => setManual({ ...manual, title: t })} flex={3} />
              <Field placeholder="Issue #" value={manual.issue_number} onChange={(t) => setManual({ ...manual, issue_number: t })} flex={1} />
            </View>
            <View className="flex-row gap-2 mt-2">
              <Field placeholder="Publisher" value={manual.publisher} onChange={(t) => setManual({ ...manual, publisher: t })} flex={2} />
              <Field placeholder="Year" value={manual.year} onChange={(t) => setManual({ ...manual, year: t.replace(/\D/g, '') })} flex={1} numeric />
            </View>
            <View className="flex-row gap-2 mt-2">
              {(['single_issue', 'annual', 'collected_edition'] as BookFormat[]).map((f) => (
                <Text
                  key={f}
                  accessibilityRole="radio"
                  accessibilityState={{ selected: manual.format === f }}
                  onPress={() => setManual({ ...manual, format: f })}
                  className="rounded-full border px-3 py-1 text-xs font-bold"
                  style={{
                    borderColor: manual.format === f ? colors.cyan : colors.ink800,
                    color: manual.format === f ? colors.cyan : colors.muted,
                  }}
                >
                  {FORMAT_LABELS[f]}
                </Text>
              ))}
            </View>
            <View className="mt-3">
              <Button label="Use these details" tone="ghost" onPress={useManual} disabled={!manualReady} />
            </View>
          </View>
        </View>

        <View className="mt-5 gap-2">
          {report.defects.map((d) => (
            <View key={d.area} className="flex-row items-center justify-between rounded-xl bg-ink-900 px-3 py-2">
              <Text className="text-white font-bold w-24">{d.area}</Text>
              <Text className="text-neutral-400 flex-1" numberOfLines={2}>
                {d.note}
              </Text>
              <Text className="text-pop-yellow font-bold ml-2">{d.score.toFixed(1)}</Text>
            </View>
          ))}
        </View>
        <Text className="text-neutral-500 mt-3 text-xs">
          Based on {report.photos_used ?? 1} photo{(report.photos_used ?? 1) === 1 ? '' : 's'}. Photos show the
          outside only: interior pages and restoration are not graded.
        </Text>

        <View className="mt-6 gap-3">
          {phase === 'saving' ? (
            <LoadingDots label="Saving to your Vault..." />
          ) : (
            <>
              <Button
                label={chosen ? `Add ${describe(chosen)} to Vault` : 'Add to Vault'}
                onPress={save}
                disabled={!chosen || value.loading}
              />
              <Button label="Retake photos" tone="ghost" onPress={reset} />
            </>
          )}
        </View>
      </ScrollView>
    );
  }

  const current = STEPS[step];
  return (
    <View className="flex-1 bg-ink-950">
      <CameraView ref={cameraRef} style={StyleSheet.absoluteFill} facing={facing} />

      {/* Step indicator */}
      <View className="absolute top-14 left-0 right-0 flex-row gap-2 px-5">
        {STEPS.map(({ role, label }, i) => {
          const done = Boolean(photos[role]) || i < step;
          const active = i === step;
          return (
            <View
              key={role}
              className="flex-1 rounded-full py-1.5 items-center border"
              style={{
                borderColor: done ? colors.green : active ? colors.yellow : colors.ink800,
                backgroundColor: '#0b0b14cc',
              }}
            >
              <Text className="text-[11px] font-bold" style={{ color: done ? colors.green : active ? colors.yellow : colors.muted }}>
                {photos[role] ? '✓ ' : ''}
                {label}
              </Text>
            </View>
          );
        })}
      </View>

      {/* Framed overlay guide */}
      <View pointerEvents="none" className="flex-1 items-center justify-center">
        <View
          className="rounded-3xl border-4 border-pop-yellow/90"
          style={current.role === 'spine' ? { width: '22%', height: '70%' } : { width: '70%', height: '70%' }}
        />
        <Text className="mt-3 text-neutral-200 text-center px-8">{current.hint}</Text>
      </View>

      {/* Controls */}
      <View className="absolute bottom-8 left-0 right-0 items-center">
        {phase === 'grading' ? (
          <View className="rounded-2xl bg-ink-900/90 px-4 py-3">
            <LoadingDots label="Identifying and grading..." />
          </View>
        ) : (
          <>
            <Text
              accessibilityRole="button"
              accessibilityLabel={`Take ${current.label.toLowerCase()} photo`}
              className="h-20 w-20 rounded-full border-4 border-pop-yellow bg-pop-red"
              onPress={onCapture}
            />
            <View className="flex-row gap-6 mt-3">
              {step > 0 ? (
                <Text className="text-pop-cyan font-bold" onPress={() => advance(photos)}>
                  {step === STEPS.length - 1 ? 'Skip and grade' : `Skip ${current.label.toLowerCase()}`}
                </Text>
              ) : null}
              <Text className="text-pop-cyan font-bold" onPress={() => setFacing((f) => (f === 'back' ? 'front' : 'back'))}>
                Flip camera
              </Text>
            </View>
            {photos.front ? (
              <View className="mt-2">
                <Pill label={`${Object.values(photos).filter(Boolean).length} of 3 photos`} color={colors.cyan} />
              </View>
            ) : null}
          </>
        )}
      </View>
    </View>
  );
}

function Field({
  placeholder,
  value,
  onChange,
  flex,
  numeric,
}: {
  placeholder: string;
  value: string;
  onChange: (text: string) => void;
  flex: number;
  numeric?: boolean;
}) {
  return (
    <TextInput
      value={value}
      onChangeText={onChange}
      placeholder={placeholder}
      placeholderTextColor={colors.muted}
      accessibilityLabel={placeholder}
      keyboardType={numeric ? 'number-pad' : 'default'}
      className="rounded-xl border bg-ink-950 px-3 py-2 text-white"
      // flexBasis/minWidth 0 so the boxes share the row instead of overflowing it.
      style={{ flexGrow: flex, flexBasis: 0, minWidth: 0, borderColor: colors.ink800 }}
    />
  );
}
