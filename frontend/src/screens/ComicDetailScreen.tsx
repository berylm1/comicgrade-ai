import React, { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Image,
  ScrollView,
  Text,
  TextInput,
  View,
} from 'react-native';
import { useFocusEffect } from '@react-navigation/native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import { api } from '../lib/api';
import type { Comic, PricePoint } from '../types';
import { GradeBadge } from '../components/ui';

type Props = NativeStackScreenProps<{ ComicDetail: { comicId: string } }, 'ComicDetail'>;

/** Individual comic detail: cover, grade, market value, price history. */
export default function ComicDetailScreen({ route }: Props) {
  const comicId = route.params.comicId;
  const [comic, setComic] = useState<Comic | null>(null);
  const [prices, setPrices] = useState<PricePoint[]>([]);
  const [priceInput, setPriceInput] = useState('');
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const [c, p] = await Promise.all([api.getComic(comicId), api.listPrices(comicId)]);
      setComic(c);
      setPrices(p);
    } catch (err: any) {
      Alert.alert('Error', err?.message ?? 'Failed to load comic');
    } finally {
      setLoading(false);
    }
  }, [comicId]);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load]),
  );

  const addPrice = async () => {
    const price = parseFloat(priceInput);
    if (!Number.isFinite(price) || price <= 0) {
      Alert.alert('Invalid price', 'Enter a positive dollar amount.');
      return;
    }
    try {
      await api.addPrice(comicId, price, 'manual');
      setPriceInput('');
      await load();
    } catch (err: any) {
      Alert.alert('Error', err?.message ?? 'Could not add price point');
    }
  };

  if (loading) {
    return <ActivityIndicator color="#ffd21f" style={{ marginTop: 120 }} />;
  }
  if (!comic) {
    return (
      <View className="flex-1 bg-ink-950 items-center justify-center">
        <Text className="text-pop-red">Comic not found.</Text>
      </View>
    );
  }

  const first = prices[0]?.price ?? null;
  const last = prices.at(-1)?.price ?? null;
  const delta = first != null && last != null ? last - first : null;

  return (
    <ScrollView className="flex-1 bg-ink-950" contentContainerStyle={{ padding: 20, paddingTop: 16 }}>
      <View className="rounded-3xl overflow-hidden bg-ink-900 border border-ink-800">
        <View className="h-72 bg-ink-800 items-center justify-center">
          {comic.cover_image_url ? (
            <Image source={{ uri: comic.cover_image_url }} className="w-full h-full" />
          ) : (
            <Text className="text-7xl">💥</Text>
          )}
        </View>
      </View>

      <View className="flex-row items-center justify-between mt-4">
        <View className="flex-1 mr-3">
          <Text className="text-white text-2xl font-bold">{comic.title}</Text>
          <Text className="text-neutral-400">
            #{comic.issue_number} · {comic.publisher}
          </Text>
          <Text className="text-pop-cyan text-xs font-bold mt-1 uppercase">
            {comic.grade_type && comic.grade_type !== 'raw'
              ? `${comic.grade_type} slab${comic.slab_cert_number ? ` · cert ${comic.slab_cert_number}` : ''}`
              : 'Raw · AI estimate'}
          </Text>
        </View>
        <GradeBadge grade={comic.estimated_grade} />
      </View>

      <View className="flex-row gap-3 mt-5">
        <View className="flex-1 rounded-2xl bg-ink-900 border border-ink-800 p-3">
          <Text className="text-[10px] uppercase tracking-widest text-neutral-400">
            Est. Market Value
          </Text>
          <Text className="text-2xl font-bold text-pop-yellow">
            {comic.current_market_value != null
              ? `$${comic.current_market_value.toFixed(2)}`
              : 'No data'}
          </Text>
          {delta != null && (
            <Text className={`text-xs font-bold ${delta >= 0 ? 'text-grade-high' : 'text-pop-red'}`}>
              {delta >= 0 ? '▲' : '▼'} ${Math.abs(delta).toFixed(2)} since first sale
            </Text>
          )}
        </View>
      </View>

      <Text className="text-neutral-400 uppercase tracking-widest text-xs font-bold mt-8 mb-2">
        Price history
      </Text>
      {prices.length === 0 ? (
        <Text className="text-neutral-400">No recorded sales yet.</Text>
      ) : (
        prices.map((p, i) => (
          <View key={i} className="flex-row justify-between rounded-xl bg-ink-900 px-4 py-3 mb-2">
            <Text className="text-neutral-300">{p.sale_date}</Text>
            <Text className="text-neutral-500 text-xs">{p.source}</Text>
            <Text className="text-pop-cyan font-bold">${p.price.toFixed(2)}</Text>
          </View>
        ))
      )}

      <View className="flex-row gap-2 mt-4">
        <TextInput
          value={priceInput}
          onChangeText={setPriceInput}
          placeholder="Add sale price (e.g. 249.99)"
          placeholderTextColor="#6b6b80"
          keyboardType="decimal-pad"
          className="flex-1 rounded-2xl bg-ink-900 border border-ink-800 px-4 py-3 text-white"
        />
        <Text
          className="rounded-2xl bg-pop-yellow px-5 py-3 font-bold text-ink-950"
          onPress={addPrice}
        >
          Log
        </Text>
      </View>
    </ScrollView>
  );
}