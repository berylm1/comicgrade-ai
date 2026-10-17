import React, { useCallback, useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  Text,
  View,
} from 'react-native';
import { useFocusEffect } from '@react-navigation/native';

import { api } from '../lib/api';
import type { Comic } from '../types';
import { StatChip } from '../components/ui';

type ValueLens = 'all' | 'raw' | 'certified';

const LENSES: { key: ValueLens; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'raw', label: 'Raw est.' },
  { key: 'certified', label: 'Slabbed' },
];

function inLens(comic: Comic, lens: ValueLens): boolean {
  if (lens === 'raw') return (comic.grade_type ?? 'raw') === 'raw';
  if (lens === 'certified') return comic.grade_type != null && comic.grade_type !== 'raw';
  return true;
}

function gradeTier(grade?: number | null): 'high' | 'mid' | 'low' | 'none' {
  if (grade == null) return 'none';
  if (grade >= 9.5) return 'high';
  if (grade >= 7) return 'mid';
  return 'low';
}

/** Valuation dashboard: aggregate stats + top-movers list. */
export default function DashboardScreen() {
  const [comics, setComics] = useState<Comic[]>([]);
  const [lens, setLens] = useState<ValueLens>('all');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useFocusEffect(
    useCallback(() => {
      api
        .listComics()
        .then((res) => {
          setComics(res);
          setError(null);
        })
        .catch((err) => setError(err?.message ?? 'Failed to load dashboard'))
        .finally(() => setLoading(false));
    }, []),
  );

  const lensComics = comics.filter((c) => inLens(c, lens));
  const valued = lensComics.filter((c) => c.current_market_value != null);
  const totalValue = valued.reduce((sum, c) => sum + (c.current_market_value ?? 0), 0);
  const graded = lensComics.filter((c) => c.estimated_grade != null);
  const avgGrade = graded.length
    ? graded.reduce((s, c) => s + (c.estimated_grade ?? 0), 0) / graded.length
    : 0;
  const gems = lensComics.filter((c) => gradeTier(c.estimated_grade) === 'high');
  const topBooks = [...valued].sort(
    (a, b) => (b.current_market_value ?? 0) - (a.current_market_value ?? 0),
  );

  return (
    <ScrollView className="flex-1 bg-ink-950" contentContainerStyle={{ padding: 20, paddingTop: 60 }}>
      <Text className="text-pop-magenta text-xs font-bold uppercase tracking-widest">
        ComicGrade AI · Valuation
      </Text>
      <Text className="text-white text-3xl font-bold mt-1">Collection Dashboard</Text>

      {/* Raw vs slabbed value lens */}
      <View className="flex-row gap-2 mt-4">
        {LENSES.map(({ key, label }) => {
          const active = lens === key;
          return (
            <Pressable
              key={key}
              onPress={() => setLens(key)}
              className={`px-4 py-2 rounded-full border ${
                active
                  ? 'border-pop-yellow bg-pop-yellow'
                  : 'border-ink-800 bg-ink-900'
              }`}
            >
              <Text className={`text-xs font-bold ${active ? 'text-ink-950' : 'text-neutral-300'}`}>
                {label}
              </Text>
            </Pressable>
          );
        })}
      </View>

      {error && <Text className="text-pop-red mt-3">{error}</Text>}

      <View className="flex-row gap-3 mt-6">
        <StatChip label="Books" value={String(lensComics.length)} />
        <StatChip label="Est. Value" value={`$${totalValue.toFixed(2)}`} />
      </View>
      <View className="flex-row gap-3 mt-3">
        <StatChip label="Avg Grade" value={avgGrade ? avgGrade.toFixed(1) : '—'} />
        <StatChip label="Gem Tier (9.5+)" value={String(gems.length)} />
      </View>

      <Text className="text-neutral-400 uppercase tracking-widest text-xs font-bold mt-8 mb-2">
        Top holdings by value
      </Text>
      {loading ? (
        <ActivityIndicator color="#ffd21f" className="mt-6" />
      ) : (
        topBooks.slice(0, 8).map((comic, i) => (
          <View
            key={comic.id}
            className="flex-row items-center rounded-2xl bg-ink-900 border border-ink-800 px-4 py-3 mb-2"
          >
            <Text className="text-pop-yellow font-bold w-6">{i + 1}</Text>
            <View className="flex-1">
              <Text className="text-white font-bold" numberOfLines={1}>
                {comic.title} #{comic.issue_number}
              </Text>
              <Text className="text-neutral-400 text-xs">
                {comic.publisher}
                {comic.estimated_grade != null ? ` · grade ${comic.estimated_grade.toFixed(1)}` : ''}
              </Text>
            </View>
            <Text className="text-pop-cyan font-bold">
              ${comic.current_market_value?.toFixed(2)}
            </Text>
          </View>
        ))
      )}
      {!loading && topBooks.length === 0 && (
        <Text className="text-neutral-400">
          No valuations yet. Add price points from a comic's detail screen.
        </Text>
      )}
    </ScrollView>
  );
}