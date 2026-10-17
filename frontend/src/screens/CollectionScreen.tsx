import React, { useCallback, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  Image,
  Pressable,
  Text,
  View,
} from 'react-native';
import { useNavigation, useFocusEffect } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';

import { api } from '../lib/api';
import type { Comic } from '../types';

type Props = { navigation: NativeStackNavigationProp<any> };

function ComicCard({ comic, onPress }: { comic: Comic; onPress: () => void }) {
  return (
    <Pressable
      onPress={onPress}
      className="mr-3 w-32 rounded-2xl overflow-hidden bg-ink-900 border border-ink-800"
    >
      <View className="h-44 bg-ink-800 items-center justify-center">
        {comic.cover_image_url ? (
          <Image source={{ uri: comic.cover_image_url }} className="w-full h-full" />
        ) : (
          <Text className="text-4xl opacity-60">💥</Text>
        )}
      </View>
      <View className="p-2">
        <Text className="text-white text-xs font-bold" numberOfLines={1}>
          {comic.title}
        </Text>
        <Text className="text-neutral-400 text-[10px]">#{comic.issue_number} · {comic.publisher}</Text>
        {comic.estimated_grade != null && (
          <Text className="text-pop-yellow text-[10px] font-bold mt-1">
            {comic.estimated_grade.toFixed(1)}
          </Text>
        )}
      </View>
    </Pressable>
  );
}

/** Scrollable grid of the user's scanned collection, grouped by publisher. */
export default function CollectionScreen({ navigation }: Props) {
  const [comics, setComics] = useState<Comic[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setError(null);
      setComics(await api.listComics());
    } catch (err: any) {
      setError(err?.message ?? 'Failed to load collection');
    } finally {
      setLoading(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load]),
  );

  const groups = comics.reduce<Record<string, Comic[]>>((acc, comic) => {
    (acc[comic.publisher] ||= []).push(comic);
    return acc;
  }, {});

  return (
    <View className="flex-1 bg-ink-950 pt-14">
      <Text className="text-pop-yellow text-2xl font-bold px-4">My Collection</Text>
      <Text className="text-neutral-400 px-4 mb-3">
        {loading ? 'Loading…' : `${comics.length} book${comics.length === 1 ? '' : 's'} scanned`}
      </Text>

      {error && <Text className="text-pop-red px-4 mb-2">{error}</Text>}

      {loading ? (
        <ActivityIndicator color="#ffd21f" className="mt-8" />
      ) : (
        <FlatList
          data={Object.entries(groups)}
          keyExtractor={([publisher]) => publisher}
          contentContainerStyle={{ paddingHorizontal: 16, paddingBottom: 24 }}
          ItemSeparatorComponent={() => <View className="h-5" />}
          renderItem={({ item: [publisher, list] }) => (
            <View>
              <Text className="text-white font-bold text-sm uppercase tracking-wider mb-2">
                {publisher} · {list.length}
              </Text>
              <FlatList
                horizontal
                data={list}
                keyExtractor={(c) => c.id}
                showsHorizontalScrollIndicator={false}
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
            <View className="mt-16 items-center">
              <Text className="text-6xl">🦸</Text>
              <Text className="text-neutral-300 mt-4 text-center">
                No comics yet — hit the Scan tab and frame your first cover!
              </Text>
            </View>
          }
        />
      )}
    </View>
  );
}