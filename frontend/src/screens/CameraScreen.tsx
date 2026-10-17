import React, { useCallback, useRef, useState } from 'react';
import { Image, Platform, Text, View, Alert, StyleSheet } from 'react-native';
import { CameraView, CameraType, useCameraPermissions } from 'expo-camera';
import * as MediaLibrary from 'expo-media-library';

import { api } from '../lib/api';
import { getSupabase } from '../lib/supabase';
import type { Comic, VisionResult } from '../types';
import { GradeBadge, LoadingDots } from '../components/ui';

type Phase = 'idle' | 'analyzing' | 'saving' | 'done' | 'error';

/**
 * Camera capture screen with framed overlay guides for covers and spines.
 * Flow: capture -> analyze (vision pipeline) -> save locally -> upload to
 * Supabase Storage -> create the comic row via the backend.
 */
export default function CameraScreen() {
  const [permission, requestPermission] = useCameraPermissions();
  const [libraryPermission] = MediaLibrary.usePermissions();
  const [facing, setFacing] = useState<CameraType>('back');
  const [phase, setPhase] = useState<Phase>('idle');
  const [hit, setHit] = useState<VisionResult | null>(null);
  const [busy, setBusy] = useState(false);
  const lastUri = useRef<string | null>(null);

  const onCapture = useCallback(async () => {
    if (!cameraRef.current || busy) return;
    try {
      setBusy(true);
      setPhase('idle');
      setHit(null);

      // 1. Capture locally (JPEG base64 in memory, no gallery permission needed).
      const photo = await cameraRef.current.takePictureAsync({
        quality: 0.85,
        imageType: 'jpg',
        base64: true,
        exif: false,
      });
      lastUri.current = photo.uri;

      // 2. Send to the AI vision pipeline.
      setPhase('analyzing');
      const result = await api.analyzeCover(photo.uri);
      setHit(result);

      // 3. Save to the device photo library (skip gracefully on web / no perms).
      if (Platform.OS !== 'web' && libraryPermission?.granted) {
        try {
          await MediaLibrary.saveToLibraryAsync(photo.uri);
        } catch {
          /* gallery save is best-effort */
        }
      }

      // 4. Upload to Supabase Storage, then register the comic via the backend.
      setPhase('saving');
      const comic = await persistComic(photo.uri, result);
      setPhase(comic ? 'done' : 'error');
      if (comic) {
        setHit(result);
      } else {
        Alert.alert('Saved analysis', 'Could not reach the backend — showing local result only.');
      }
    } catch (err: any) {
      setPhase('error');
      Alert.alert('Scan failed', err?.message ?? 'Unknown error');
    } finally {
      setBusy(false);
    }
  }, [busy, libraryPermission]);

  const cameraRef = useRef<CameraView>(null);

  if (!permission?.granted) {
    return (
      <View className="flex-1 items-center justify-center bg-ink-950 px-6">
        <Text className="text-pop-yellow text-2xl font-bold">Camera access needed</Text>
        <Text className="text-neutral-400 mt-2 text-center">
          ComicGrade AI uses the camera to scan comic covers and spines.
        </Text>
        <Text
          className="mt-6 rounded-2xl bg-pop-yellow px-8 py-3 font-bold text-ink-950"
          onPress={() => requestPermission()}
        >
          Grant camera access
        </Text>
      </View>
    );
  }

  return (
    <View className="flex-1 bg-ink-950">
      <CameraView ref={cameraRef} style={StyleSheet.absoluteFill} facing={facing} />

      {/* Framed overlay guide: cover reticle + spine strip */}
      <View pointerEvents="none" className="flex-1">
        <View className="flex-1 items-center justify-center">
          <View className="w-[78%] h-[78%] rounded-3xl border-4 border-pop-yellow/90">
            <View className="absolute -left-1 -top-1 w-8 h-8 border-l-4 border-t-4 border-pop-magenta rounded-tl-3xl" />
            <View className="absolute -right-1 -top-1 w-8 h-8 border-r-4 border-t-4 border-pop-magenta rounded-tr-3xl" />
            <View className="absolute -left-1 -bottom-1 w-8 h-8 border-l-4 border-b-4 border-pop-magenta rounded-bl-3xl" />
            <View className="absolute -right-1 -bottom-1 w-8 h-8 border-r-4 border-b-4 border-pop-magenta rounded-br-3xl" />
          </View>
          <Text className="mt-3 text-neutral-200 text-center px-8">
            Center the cover in the frame — or rotate for a spine scan (vertical bar)
          </Text>
          <View className="absolute right-4 top-1/4 h-1/2 w-10 rounded-lg border-2 border-dashed border-pop-cyan/80" />
        </View>
      </View>

      {/* Control strip */}
      <View className="absolute bottom-8 left-0 right-0 items-center">
        {busy ? (
          <View className="rounded-2xl bg-ink-900/90 px-4 py-3">
            <LoadingDots
              label={phase === 'analyzing' ? 'Identifying cover...' : 'Uploading & grading...'}
            />
          </View>
        ) : (
          <Text
            className="h-20 w-20 rounded-full border-4 border-pop-yellow bg-pop-red"
            onPress={onCapture}
          />
        )}
        {!busy && hit && (
          <View className="mt-3 rounded-2xl bg-ink-900/95 px-4 py-3 border border-pop-cyan/40">
            <Text className="text-pop-yellow font-bold">
              {hit.title} #{hit.issue_number} · {hit.publisher}
            </Text>
            <View className="flex-row items-center gap-2 mt-1">
              <GradeBadge grade={hit.tentative_grade} />
              <Text className="text-neutral-400 flex-1" numberOfLines={1}>
                {hit.notes || 'Tentative AI grade'}
              </Text>
            </View>
          </View>
        )}
        {!busy && (
          <Text
            className="absolute right-6 bottom-1 text-pop-cyan font-bold"
            onPress={() => setFacing((f) => (f === 'back' ? 'front' : 'back'))}
          >
            Flip
          </Text>
        )}
      </View>
    </View>
  );
}

/** Upload the captured file to Supabase Storage and create the comic row. */
async function persistComic(uri: string, result: VisionResult): Promise<Comic | null> {
  try {
    const sb = getSupabase();
    // createComic first so we have an id path for the storage object.
    const draft = await api.createComic({
      title: result.title,
      issue_number: result.issue_number,
      publisher: result.publisher,
      estimated_grade: result.tentative_grade,
    });

    const res = await fetch(uri);
    const blob = await res.blob();
    const path = `${draft.id}/cover.jpg`;
    const { error } = await sb.storage.from('cover-images').upload(path, blob, {
      contentType: 'image/jpeg',
      upsert: true,
    });
    if (error) throw error;
    const { data } = sb.storage.from('cover-images').getPublicUrl(path);

    const committed = await api.createComic({
      id: draft.id,
      title: draft.title,
      issue_number: draft.issue_number,
      publisher: draft.publisher,
      cover_image_url: data.publicUrl,
      estimated_grade: result.tentative_grade,
    });
    return committed ?? draft;
  } catch (err) {
    console.warn('[ComicGrade] persistComic failed:', err);
    return null;
  }
}