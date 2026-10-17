/** Small shared UI atoms for the comic-pop theme. */
import React from 'react';
import { Text, View, ActivityIndicator } from 'react-native';

export function GradeBadge({ grade }: { grade?: number | null }) {
  if (grade == null) return null;
  const tone =
    grade >= 9.5
      ? 'text-grade-high'
      : grade >= 7
      ? 'text-grade-mid'
      : 'text-grade-low';
  return (
    <View className="rounded-full border-2 border-pop-magenta bg-ink-800 px-2 py-1">
      <Text className={`text-xs font-bold ${tone}`}>{grade.toFixed(1)}</Text>
    </View>
  );
}

export function StatChip({ label, value }: { label: string; value: string }) {
  return (
    <View className="flex-1 rounded-2xl bg-ink-900 border border-ink-800 px-3 py-3">
      <Text className="text-[10px] uppercase tracking-widest text-neutral-400">{label}</Text>
      <Text className="text-lg font-bold text-pop-yellow mt-1">{value}</Text>
    </View>
  );
}

export function LoadingDots({ label = 'Grading...' }: { label?: string }) {
  return (
    <View className="flex-row items-center gap-2">
      <ActivityIndicator color="#ffd21f" size="small" />
      <Text className="text-neutral-300">{label}</Text>
    </View>
  );
}