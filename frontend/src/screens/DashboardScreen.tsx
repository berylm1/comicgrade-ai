import React, { useCallback, useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, Text, View } from 'react-native';
import { useFocusEffect } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';

import { api } from '../lib/api';
import { DEMO_MODE } from '../lib/env';
import { AUTH_ENABLED, useAuth } from '../lib/auth';
import { buildReport } from '../lib/grading';
import type { Comic, ValueLens } from '../types';
import {
  colors,
  Delta,
  DemoTag,
  GradeBadge,
  isRaw,
  SectionTitle,
  SegmentedControl,
  StatChip,
  usd,
  useAppWidth,
} from '../components/ui';
import { AreaChart, CoverArt } from '../components/visuals';

type Props = { navigation: NativeStackNavigationProp<any> };

const LENSES: { key: ValueLens; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'raw', label: 'Raw est.' },
  { key: 'certified', label: 'Slabbed' },
];

function inLens(comic: Comic, lens: ValueLens): boolean {
  if (lens === 'raw') return isRaw(comic.grade_type);
  if (lens === 'certified') return !isRaw(comic.grade_type);
  return true;
}

/** Valuation dashboard: collection value over time, headline stats, top holdings. */
export default function DashboardScreen({ navigation }: Props) {
  const width = useAppWidth();
  const { signOut } = useAuth();
  const [comics, setComics] = useState<Comic[]>([]);
  const [history, setHistory] = useState<number[]>([]);
  const [lens, setLens] = useState<ValueLens>('all');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useFocusEffect(
    useCallback(() => {
      let live = true;
      Promise.all([api.listComics(), api.portfolioHistory(lens)])
        .then(([list, series]) => {
          if (!live) return;
          setComics(list);
          setHistory(series);
          setError(null);
        })
        .catch((err) => live && setError(err?.message ?? 'Failed to load dashboard'))
        .finally(() => live && setLoading(false));
      return () => {
        live = false;
      };
    }, [lens]),
  );

  const lensComics = comics.filter((c) => inLens(c, lens));
  const valued = lensComics.filter((c) => c.current_market_value != null);
  const totalValue = valued.reduce((sum, c) => sum + (c.current_market_value ?? 0), 0);
  const graded = lensComics.filter((c) => c.estimated_grade != null);
  const avgGrade = graded.length
    ? graded.reduce((s, c) => s + (c.estimated_grade ?? 0), 0) / graded.length
    : 0;
  const gems = lensComics.filter((c) => (c.estimated_grade ?? 0) >= 9.5);
  const topBooks = [...valued].sort(
    (a, b) => (b.current_market_value ?? 0) - (a.current_market_value ?? 0),
  );

  const start = history[0];
  const gain = history.length > 1 ? totalValue - start : null;
  const gainPct = gain != null && start ? (gain / start) * 100 : null;

  // Pre-screen teaser: the raw book with the biggest payoff from professional grading.
  const bestSubmit = DEMO_MODE
    ? comics
        .filter((c) => isRaw(c.grade_type))
        .map((c) => ({ comic: c, slab: buildReport(c).slab }))
        .filter((x) => x.slab?.verdict === 'submit')
        .sort((a, b) => (b.slab?.net_uplift ?? 0) - (a.slab?.net_uplift ?? 0))[0]
    : undefined;

  const open = (comic: Comic) => navigation.navigate('ComicDetail', { comicId: comic.id });

  return (
    <ScrollView className="flex-1 bg-ink-950" contentContainerStyle={{ padding: 20, paddingTop: 56, paddingBottom: 32 }}>
      <View className="flex-row items-center justify-between">
        <Text className="text-pop-magenta text-xs font-bold uppercase tracking-widest">ComicGrade AI</Text>
        {DEMO_MODE && <DemoTag />}
        {AUTH_ENABLED && (
          <Text className="text-pop-cyan text-xs font-bold" accessibilityRole="button" onPress={signOut}>
            Sign out
          </Text>
        )}
      </View>
      <Text className="text-white text-4xl font-display uppercase mt-1">Your Vault</Text>

      <View className="mt-4">
        <SegmentedControl options={LENSES} value={lens} onChange={setLens} />
      </View>

      {error && <Text className="text-pop-red mt-3">{error}</Text>}

      {/* Value hero */}
      <View className="rounded-3xl bg-ink-900 border border-ink-800 mt-4 overflow-hidden">
        <View className="px-5 pt-5">
          <Text className="text-[10px] uppercase tracking-widest text-neutral-400">Estimated collection value</Text>
          <Text className="text-pop-yellow text-5xl font-display mt-1">{usd(totalValue)}</Text>
          {gain != null && (
            <View className="flex-row items-center gap-2 mt-1">
              <Delta pct={gainPct} />
              <Text className="text-neutral-400 text-xs">
                {gain >= 0 ? '+' : '-'}
                {usd(Math.abs(gain))} over {history.length} months
              </Text>
            </View>
          )}
        </View>
        {history.length > 1 ? (
          <AreaChart points={history} width={width - 42} height={110} color={colors.cyan} />
        ) : (
          <View className="h-5" />
        )}
      </View>

      <View className="flex-row gap-3 mt-3">
        <StatChip label="Books" value={String(lensComics.length)} tone="#fff" />
        <StatChip label="Avg grade" value={avgGrade ? avgGrade.toFixed(1) : 'n/a'} />
        <StatChip label="Gem 9.5+" value={String(gems.length)} tone={colors.green} />
      </View>

      {bestSubmit?.slab && lens !== 'certified' && (
        <Pressable
          onPress={() => navigation.navigate('Insights')}
          className="flex-row items-center rounded-3xl border border-pop-yellow mt-4 p-4"
          style={{ backgroundColor: '#ffd21f14' }}
        >
          <CoverArt comic={bestSubmit.comic} width={52} />
          <View className="flex-1 ml-4">
            <Text className="text-pop-yellow text-[10px] font-bold uppercase tracking-widest">Pre-screen pick</Text>
            <Text className="text-white font-bold mt-1" numberOfLines={1}>
              {bestSubmit.comic.title} #{bestSubmit.comic.issue_number}
            </Text>
            <Text className="text-neutral-300 text-xs mt-1">
              Slabbing could net <Text className="text-grade-high font-bold">+{usd(bestSubmit.slab.net_uplift)}</Text> after fees
            </Text>
          </View>
          <Text className="text-pop-yellow text-2xl">›</Text>
        </Pressable>
      )}

      <SectionTitle action="See all" onAction={() => navigation.navigate('Collection')}>
        Top holdings
      </SectionTitle>
      {loading ? (
        <ActivityIndicator color={colors.yellow} className="mt-6" />
      ) : (
        topBooks.slice(0, 6).map((comic, i) => (
          <Pressable
            key={comic.id}
            onPress={() => open(comic)}
            className="flex-row items-center rounded-2xl bg-ink-900 border border-ink-800 px-3 py-2.5 mb-2"
          >
            <Text className="text-neutral-500 font-display text-lg w-6">{i + 1}</Text>
            <CoverArt comic={comic} width={34} />
            <View className="flex-1 ml-3">
              <Text className="text-white font-bold" numberOfLines={1}>
                {comic.title} #{comic.issue_number}
              </Text>
              <View className="flex-row items-center gap-2 mt-1">
                <GradeBadge grade={comic.estimated_grade} type={comic.grade_type} />
                <Text className="text-neutral-400 text-xs">{comic.publisher}</Text>
              </View>
            </View>
            <View className="items-end">
              <Text className="text-white font-bold">{usd(comic.current_market_value)}</Text>
              <Delta pct={comic.change_pct} />
            </View>
          </Pressable>
        ))
      )}
      {!loading && topBooks.length === 0 && (
        <Text className="text-neutral-400">No valuations yet. Scan a book or log a price to get started.</Text>
      )}
    </ScrollView>
  );
}
