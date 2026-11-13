import React, { useCallback, useState } from 'react';
import { ActivityIndicator, FlatList, Pressable, ScrollView, Text, TextInput, View } from 'react-native';
import { useFocusEffect } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';

import { api } from '../lib/api';
import type { Comic } from '../types';
import { colors, GradeBadge, isRaw, usd } from '../components/ui';
import { CoverArt } from '../components/visuals';

type Props = { navigation: NativeStackNavigationProp<any> };
type Filter = 'all' | 'keys' | 'raw' | 'slabbed' | 'gems';

const FILTERS: { key: Filter; label: string; test: (c: Comic) => boolean }[] = [
  { key: 'all', label: 'All', test: () => true },
  { key: 'keys', label: 'Key issues', test: (c) => !!c.key_note },
  { key: 'raw', label: 'Raw', test: (c) => isRaw(c.grade_type) },
  { key: 'slabbed', label: 'Slabbed', test: (c) => !isRaw(c.grade_type) },
  { key: 'gems', label: 'Gem 9.5+', test: (c) => (c.estimated_grade ?? 0) >= 9.5 },
];

function ComicCard({ comic, onPress }: { comic: Comic; onPress: () => void }) {
  return (
    <Pressable onPress={onPress} className="mr-3" style={{ width: 112 }}>
      <View>
        <CoverArt comic={comic} width={112} />
        <View className="absolute right-1.5 bottom-1.5">
          <GradeBadge grade={comic.estimated_grade} type={comic.grade_type} />
        </View>
      </View>
      <Text className="text-white text-xs font-bold mt-2" numberOfLines={1}>
        {comic.title}
      </Text>
      <View className="flex-row justify-between">
        <Text className="text-neutral-400 text-[11px]">#{comic.issue_number}</Text>
        <Text className="text-pop-yellow text-[11px] font-bold">{usd(comic.current_market_value)}</Text>
      </View>
    </Pressable>
  );
}

/** The scanned collection, searchable and grouped by publisher. */
export default function CollectionScreen({ navigation }: Props) {
  const [comics, setComics] = useState<Comic[]>([]);
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState<Filter>('all');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useFocusEffect(
    useCallback(() => {
      api
        .listComics()
        .then((list) => {
          setComics(list);
          setError(null);
        })
        .catch((err) => setError(err?.message ?? 'Failed to load collection'))
        .finally(() => setLoading(false));
    }, []),
  );

  const test = FILTERS.find((f) => f.key === filter)!.test;
  const q = query.trim().toLowerCase();
  const visible = comics.filter(
    (c) => test(c) && (!q || `${c.title} ${c.issue_number} ${c.publisher}`.toLowerCase().includes(q)),
  );
  const groups = visible.reduce<Record<string, Comic[]>>((acc, comic) => {
    (acc[comic.publisher] ||= []).push(comic);
    return acc;
  }, {});

  return (
    <View className="flex-1 bg-ink-950 pt-14">
      <View className="px-5">
        <Text className="text-white text-4xl font-display uppercase">Collection</Text>
        <Text className="text-neutral-400 mb-3">
          {loading ? 'Loading…' : `${visible.length} of ${comics.length} book${comics.length === 1 ? '' : 's'}`}
        </Text>
        <TextInput
          value={query}
          onChangeText={setQuery}
          placeholder="Search title, issue or publisher"
          placeholderTextColor="#6b6b80"
          className="rounded-2xl bg-ink-900 border border-ink-800 px-4 py-3 text-white"
        />
      </View>

      <View>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ paddingHorizontal: 20, paddingVertical: 12, gap: 8 }}>
          {FILTERS.map(({ key, label }) => {
            const active = key === filter;
            return (
              <Pressable
                key={key}
                onPress={() => setFilter(key)}
                className={`px-3.5 py-1.5 rounded-full border ${active ? 'border-pop-yellow bg-pop-yellow' : 'border-ink-800 bg-ink-900'}`}
              >
                <Text className={`text-xs font-bold ${active ? 'text-ink-950' : 'text-neutral-300'}`}>{label}</Text>
              </Pressable>
            );
          })}
        </ScrollView>
      </View>

      {error && <Text className="text-pop-red px-5 mb-2">{error}</Text>}

      {loading ? (
        <ActivityIndicator color={colors.yellow} className="mt-8" />
      ) : (
        <FlatList
          data={Object.entries(groups)}
          keyExtractor={([publisher]) => publisher}
          contentContainerStyle={{ paddingBottom: 24 }}
          ItemSeparatorComponent={() => <View className="h-6" />}
          renderItem={({ item: [publisher, list] }) => (
            <View>
              <View className="flex-row items-end justify-between px-5 mb-2">
                <Text className="text-white font-display text-lg uppercase tracking-wide">{publisher}</Text>
                <Text className="text-neutral-400 text-xs">
                  {list.length} · {usd(list.reduce((s, c) => s + (c.current_market_value ?? 0), 0))}
                </Text>
              </View>
              <FlatList
                horizontal
                data={list}
                keyExtractor={(c) => c.id}
                showsHorizontalScrollIndicator={false}
                contentContainerStyle={{ paddingLeft: 20, paddingRight: 8 }}
                renderItem={({ item: comic }) => (
                  <ComicCard
                    comic={comic}
                    onPress={() => navigation.navigate('ComicDetail', { comicId: comic.id })}
                  />
                )}
              />
            </View>
          )}
          ListEmptyComponent={
            <View className="mt-16 items-center px-8">
              <Text className="text-white font-display text-2xl uppercase">Nothing here yet</Text>
              <Text className="text-neutral-400 mt-2 text-center">
                {comics.length ? 'No books match that search.' : 'Open the Scan tab and frame your first cover.'}
              </Text>
            </View>
          }
        />
      )}
    </View>
  );
}
