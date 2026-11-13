import React, { useCallback, useRef, useState } from 'react';
import { Alert, Image, Platform, ScrollView, StyleSheet, Text, View } from 'react-native';
import { CameraView, CameraType, useCameraPermissions } from 'expo-camera';
import * as MediaLibrary from 'expo-media-library';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';

import { api } from '../lib/api';
import { toScanMatch } from '../lib/scan';
import type { ScanMatch, ScanPhotos } from '../types';
import { Button, GradeBadge, LoadingDots, Pill, colors, usd } from '../components/ui';

type Props = { navigation: NativeStackNavigationProp<any> };
type Phase = 'capture' | 'grading' | 'review' | 'saving';
type Role = keyof ScanPhotos;

const STEPS: { role: Role; label: string; hint: string }[] = [
  { role: 'front', label: 'Front', hint: 'Center the front cover in the frame' },
  { role: 'back', label: 'Back', hint: 'Flip the book and frame the back cover' },
  { role: 'spine', label: 'Spine', hint: 'Turn the book so the spine faces the camera' },
];

/**
 * Live camera scan (used when demo mode is off). Guides the user through three
 * photos (front, back, spine; back and spine can be skipped), sends them to
 * POST /vision/grade, shows the result, and saves the book with its report.
 */
export default function LiveScanner({ navigation }: Props) {
  const [permission, requestPermission] = useCameraPermissions();
  const [libraryPermission] = MediaLibrary.usePermissions();
  const [facing, setFacing] = useState<CameraType>('back');
  const [phase, setPhase] = useState<Phase>('capture');
  const [step, setStep] = useState(0);
  const [photos, setPhotos] = useState<Partial<ScanPhotos>>({});
  const [match, setMatch] = useState<ScanMatch | null>(null);
  const cameraRef = useRef<CameraView>(null);

  const reset = useCallback(() => {
    setPhotos({});
    setStep(0);
    setMatch(null);
    setPhase('capture');
  }, []);

  const grade = useCallback(async (taken: Partial<ScanPhotos>) => {
    if (!taken.front) return;
    setPhase('grading');
    try {
      const result = await api.gradeScan({ front: taken.front, back: taken.back, spine: taken.spine });
      setMatch(toScanMatch(result));
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

  const save = useCallback(async () => {
    if (!match) return;
    setPhase('saving');
    try {
      const comic = await api.saveScan(match, photos.front);
      reset();
      navigation.navigate('ComicDetail', { comicId: comic.id });
    } catch (err: any) {
      setPhase('review');
      Alert.alert('Could not save', err?.message ?? 'Unknown error');
    }
  }, [match, navigation, photos.front, reset]);

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

  if ((phase === 'review' || phase === 'saving') && match) {
    const { comic, report } = match;
    return (
      <ScrollView className="flex-1 bg-ink-950" contentContainerStyle={{ padding: 20, paddingTop: 56 }}>
        <Text className="text-white text-4xl font-display uppercase">Result</Text>
        <View className="flex-row gap-3 mt-4">
          {photos.front ? (
            <Image source={{ uri: photos.front }} style={{ width: 96, height: 144, borderRadius: 12 }} />
          ) : null}
          <View className="flex-1">
            <Text className="text-pop-yellow text-xl font-bold">
              {comic.title} #{comic.issue_number}
            </Text>
            <Text className="text-neutral-400">
              {comic.publisher}
              {comic.year ? ` · ${comic.year}` : ''}
            </Text>
            {comic.key_note ? <Text className="text-pop-cyan mt-1">{comic.key_note}</Text> : null}
            <View className="flex-row items-center gap-2 mt-2">
              <GradeBadge grade={report.grade} />
              <Text className="text-neutral-300">
                Likely {report.grade_low} to {report.grade_high}
              </Text>
            </View>
            <Text className="text-neutral-400 mt-1">
              Raw value {usd(comic.current_market_value)} · {Math.round(match.match_confidence * 100)}% match
            </Text>
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
              <Button label="Add to Vault" onPress={save} />
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
