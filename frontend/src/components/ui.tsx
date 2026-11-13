/** Shared UI atoms for the comic-pop theme. */
import React, { useEffect, useRef } from 'react';
import { ActivityIndicator, Animated, Platform, Pressable, Text, View, useWindowDimensions } from 'react-native';

export const colors = {
  ink950: '#0a0a12',
  ink900: '#12121f',
  ink800: '#1c1c2e',
  yellow: '#ffd21f',
  red: '#ff3b3b',
  blue: '#2f6bff',
  cyan: '#35e0d2',
  magenta: '#ff2fb9',
  green: '#3ddc84',
  orange: '#ff6b3b',
  muted: '#8a8aa0',
};

/** Width of the phone frame the web demo is presented in. */
export const FRAME_WIDTH = 402;
export const FRAME_HEIGHT = 860;

/** True when the app is shown inside a phone frame on a wide browser window. */
export function useFramed(): boolean {
  const { width } = useWindowDimensions();
  return Platform.OS === 'web' && width > 520;
}

/** Usable screen width: the phone frame on desktop web, the window elsewhere. */
export function useAppWidth(): number {
  const { width } = useWindowDimensions();
  // The frame has a 4px border on each side.
  return useFramed() ? FRAME_WIDTH - 8 : width;
}

export function usd(value?: number | null, cents = false): string {
  if (value == null) return 'No data';
  return `$${value.toLocaleString('en-US', {
    minimumFractionDigits: cents ? 2 : 0,
    maximumFractionDigits: cents ? 2 : 0,
  })}`;
}

export function gradeColor(grade?: number | null): string {
  if (grade == null) return colors.muted;
  return grade >= 9.5 ? colors.green : grade >= 7 ? colors.yellow : colors.orange;
}

export function isRaw(gradeType?: string | null): boolean {
  return (gradeType ?? 'raw') === 'raw';
}

export function GradeBadge({ grade, type }: { grade?: number | null; type?: string | null }) {
  if (grade == null) return null;
  const raw = isRaw(type);
  return (
    <View
      className="flex-row items-center rounded-md px-1.5 py-0.5"
      style={{ backgroundColor: raw ? colors.ink800 : colors.blue }}
    >
      <Text className="text-[9px] font-bold text-white/70 mr-1">{raw ? 'AI' : (type ?? '').toUpperCase()}</Text>
      <Text className="text-xs font-bold" style={{ color: raw ? gradeColor(grade) : '#fff' }}>
        {grade.toFixed(1)}
      </Text>
    </View>
  );
}

export function StatChip({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <View className="flex-1 rounded-2xl bg-ink-900 border border-ink-800 px-3 py-3">
      <Text className="text-[10px] uppercase tracking-widest text-neutral-400">{label}</Text>
      <Text className="text-2xl font-display mt-1" style={{ color: tone ?? colors.yellow }}>
        {value}
      </Text>
    </View>
  );
}

export function SectionTitle({ children, action, onAction }: { children: string; action?: string; onAction?: () => void }) {
  return (
    <View className="flex-row items-end justify-between mt-7 mb-3">
      <Text className="text-white text-lg font-display uppercase tracking-wide">{children}</Text>
      {action && (
        <Text className="text-pop-cyan text-xs font-bold" onPress={onAction}>
          {action}
        </Text>
      )}
    </View>
  );
}

export function Pill({ label, color = colors.cyan, solid = false }: { label: string; color?: string; solid?: boolean }) {
  return (
    <View
      className="self-start rounded-full px-2.5 py-1"
      style={{ backgroundColor: solid ? color : `${color}22`, borderWidth: 1, borderColor: color }}
    >
      <Text className="text-[10px] font-bold uppercase tracking-wider" style={{ color: solid ? colors.ink950 : color }}>
        {label}
      </Text>
    </View>
  );
}

export function Delta({ pct, suffix = '' }: { pct?: number | null; suffix?: string }) {
  if (pct == null) return null;
  const up = pct >= 0;
  return (
    <Text className="text-xs font-bold" style={{ color: up ? colors.green : colors.red }}>
      {up ? '▲' : '▼'} {Math.abs(pct).toFixed(1)}%{suffix}
    </Text>
  );
}

export function Button({
  label,
  onPress,
  tone = 'primary',
  disabled,
}: {
  label: string;
  onPress?: () => void;
  tone?: 'primary' | 'ghost';
  disabled?: boolean;
}) {
  const primary = tone === 'primary';
  return (
    <Pressable
      onPress={disabled ? undefined : onPress}
      className={`items-center rounded-2xl px-5 py-3 ${primary ? 'bg-pop-yellow' : 'border border-pop-cyan'}`}
      style={{ opacity: disabled ? 0.5 : 1 }}
    >
      <Text className={`font-bold ${primary ? 'text-ink-950' : 'text-pop-cyan'}`}>{label}</Text>
    </Pressable>
  );
}

export function SegmentedControl<T extends string>({
  options,
  value,
  onChange,
}: {
  options: { key: T; label: string }[];
  value: T;
  onChange: (key: T) => void;
}) {
  return (
    <View className="flex-row rounded-full bg-ink-900 border border-ink-800 p-1 self-start">
      {options.map(({ key, label }) => {
        const active = key === value;
        return (
          <Pressable
            key={key}
            onPress={() => onChange(key)}
            className={`px-4 py-1.5 rounded-full ${active ? 'bg-pop-yellow' : ''}`}
          >
            <Text className={`text-xs font-bold ${active ? 'text-ink-950' : 'text-neutral-400'}`}>{label}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

export function LoadingDots({ label = 'Grading...' }: { label?: string }) {
  return (
    <View className="flex-row items-center gap-2">
      <ActivityIndicator color={colors.yellow} size="small" />
      <Text className="text-neutral-300">{label}</Text>
    </View>
  );
}

/** Inline, auto-dismissing confirmation. Works on web, where Alert.alert is a no-op. */
export function Toast({ message, onDone }: { message: string | null; onDone: () => void }) {
  const opacity = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    if (!message) return;
    Animated.sequence([
      Animated.timing(opacity, { toValue: 1, duration: 180, useNativeDriver: true }),
      Animated.delay(2400),
      Animated.timing(opacity, { toValue: 0, duration: 250, useNativeDriver: true }),
    ]).start(() => onDone());
  }, [message, onDone, opacity]);
  if (!message) return null;
  return (
    <Animated.View
      pointerEvents="none"
      className="absolute left-5 right-5 bottom-6 rounded-2xl bg-ink-800 border border-pop-cyan px-4 py-3"
      style={{ opacity }}
    >
      <Text className="text-white text-sm font-bold">{message}</Text>
    </Animated.View>
  );
}

export function DemoTag() {
  return <Pill label="Demo data" color={colors.magenta} />;
}
