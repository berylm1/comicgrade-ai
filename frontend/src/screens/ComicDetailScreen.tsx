import React, { useCallback, useState } from 'react';
import { ActivityIndicator, ScrollView, Text, TextInput, View } from 'react-native';
import { useFocusEffect } from '@react-navigation/native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import { api } from '../lib/api';
import type { Comic, GradeReport, PricePoint } from '../types';
import { Button, colors, Delta, isRaw, Pill, SectionTitle, Toast, usd, useAppWidth } from '../components/ui';
import { AreaChart, CoverArt, DefectBar, GradeDial } from '../components/visuals';

type Props = NativeStackScreenProps<{ ComicDetail: { comicId: string } }, 'ComicDetail'>;

const VERDICT = {
  submit: { label: 'Worth submitting', color: colors.green },
  hold: { label: 'Marginal · hold', color: colors.yellow },
  skip: { label: 'Keep it raw', color: colors.orange },
} as const;

function Row({ label, value, tone = '#fff' }: { label: string; value: string; tone?: string }) {
  return (
    <View className="flex-row justify-between py-1.5">
      <Text className="text-neutral-400 text-sm">{label}</Text>
      <Text className="text-sm font-bold" style={{ color: tone }}>
        {value}
      </Text>
    </View>
  );
}

/** Individual comic: cover, explainable grade, value history, slab decision. */
export default function ComicDetailScreen({ route }: Props) {
  const comicId = route.params.comicId;
  const width = useAppWidth();
  const [comic, setComic] = useState<Comic | null>(null);
  const [prices, setPrices] = useState<PricePoint[]>([]);
  const [report, setReport] = useState<GradeReport | null>(null);
  const [priceInput, setPriceInput] = useState('');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const clearToast = useCallback(() => setToast(null), []);

  const load = useCallback(async () => {
    try {
      const [c, p, r] = await Promise.all([
        api.getComic(comicId),
        api.listPrices(comicId),
        api.getGradeReport(comicId),
      ]);
      setComic(c);
      setPrices(p);
      setReport(r);
    } catch (err: any) {
      setToast(err?.message ?? 'Failed to load comic');
    } finally {
      setLoading(false);
    }
  }, [comicId]);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load]),
  );

  const refreshValue = async () => {
    setRefreshing(true);
    try {
      const point = await api.refreshValue(comicId);
      setToast(`Value refreshed: ${usd(point.price, true)} via ${point.source}`);
      await load();
    } catch (err: any) {
      setToast(err?.message ?? 'Could not refresh value');
    } finally {
      setRefreshing(false);
    }
  };

  const addPrice = async () => {
    const price = parseFloat(priceInput);
    if (!Number.isFinite(price) || price <= 0) {
      setToast('Enter a positive dollar amount.');
      return;
    }
    try {
      await api.addPrice(comicId, price, 'manual');
      setPriceInput('');
      setToast(`Logged ${usd(price, true)}`);
      await load();
    } catch (err: any) {
      setToast(err?.message ?? 'Could not add price point');
    }
  };

  if (loading) {
    return (
      <View className="flex-1 bg-ink-950">
        <ActivityIndicator color={colors.yellow} style={{ marginTop: 120 }} />
      </View>
    );
  }
  if (!comic) {
    return (
      <View className="flex-1 bg-ink-950 items-center justify-center">
        <Text className="text-pop-red">Comic not found.</Text>
      </View>
    );
  }

  const raw = isRaw(comic.grade_type);
  const first = prices[0]?.price ?? null;
  const last = prices.at(-1)?.price ?? null;
  const deltaPct = first && last != null && prices.length > 1 ? (last / first - 1) * 100 : null;
  const slab = report?.slab;

  return (
    <View className="flex-1 bg-ink-950">
      <ScrollView contentContainerStyle={{ padding: 20, paddingTop: 8, paddingBottom: 40 }}>
        {/* Cover + identity */}
        <View className="flex-row">
          <CoverArt comic={comic} width={132} />
          <View className="flex-1 ml-4 justify-between">
            <View>
              <Text className="text-neutral-400 text-xs uppercase tracking-widest">
                {comic.publisher}
                {comic.year ? ` · ${comic.year}` : ''}
              </Text>
              <Text className="text-white text-3xl font-display uppercase mt-1">{comic.title}</Text>
              <Text className="text-pop-yellow text-2xl font-display">#{comic.issue_number}</Text>
            </View>
            <View className="gap-2">
              {comic.key_note && <Pill label="Key issue" color={colors.magenta} />}
              {raw ? (
                <Pill label="Raw · AI estimate" color={colors.cyan} />
              ) : (
                <Pill label={`${comic.grade_type} certified`} color={colors.blue} solid />
              )}
            </View>
          </View>
        </View>
        {comic.key_note && <Text className="text-neutral-300 text-sm mt-3">{comic.key_note}</Text>}
        {!raw && comic.slab_cert_number && (
          <Text className="text-neutral-500 text-xs mt-1">Cert #{comic.slab_cert_number}</Text>
        )}

        {/* Grade */}
        <SectionTitle>{raw ? 'AI grade estimate' : 'Certified grade'}</SectionTitle>
        <View className="rounded-3xl bg-ink-900 border border-ink-800 p-4">
          <View className="flex-row items-center">
            <GradeDial grade={comic.estimated_grade ?? 0} />
            <View className="flex-1 ml-4">
              {report && raw ? (
                <>
                  <Text className="text-[10px] uppercase tracking-widest text-neutral-400">Likely range</Text>
                  <Text className="text-white text-2xl font-display">
                    {report.grade_low.toFixed(1)} to {report.grade_high.toFixed(1)}
                  </Text>
                  <Text className="text-neutral-400 text-xs mt-1">
                    {Math.round(report.confidence * 100)}% of books we place here certify inside this range
                  </Text>
                </>
              ) : (
                <Text className="text-neutral-300 text-sm">
                  {raw
                    ? 'Tentative grade from the cover scan.'
                    : 'Grade assigned by a third-party service and sealed in the slab. Shown as certified, never re-estimated.'}
                </Text>
              )}
            </View>
          </View>

          {report && raw && (
            <>
              <View className="h-px bg-ink-800 my-4" />
              <Text className="text-[10px] uppercase tracking-widest text-neutral-400 mb-3">
                Why this grade
              </Text>
              {report.defects.map((d) => (
                <DefectBar key={d.area} defect={d} />
              ))}
              {report.exterior_only && (
                <View className="rounded-xl bg-ink-800 px-3 py-2 mt-1">
                  <Text className="text-neutral-300 text-[11px]">
                    Exterior only. Photos cannot detect restoration, missing pages or interior damage.
                  </Text>
                </View>
              )}
            </>
          )}
        </View>

        {/* Value */}
        <SectionTitle>Market value</SectionTitle>
        <View className="rounded-3xl bg-ink-900 border border-ink-800 overflow-hidden">
          <View className="flex-row items-start justify-between px-4 pt-4">
            <View>
              <Text className="text-[10px] uppercase tracking-widest text-neutral-400">
                {raw ? 'Raw estimate' : 'Slabbed fair market value'}
              </Text>
              <Text className="text-pop-yellow text-4xl font-display mt-1">{usd(comic.current_market_value)}</Text>
              <Delta pct={deltaPct} suffix=" since first sale" />
            </View>
            <Button label={refreshing ? 'Refreshing…' : '↻ Refresh'} tone="ghost" onPress={refreshValue} disabled={refreshing} />
          </View>
          {prices.length > 1 ? (
            <AreaChart
              points={prices.map((p) => p.price)}
              width={width - 42}
              height={96}
              color={(deltaPct ?? 0) >= 0 ? colors.green : colors.red}
            />
          ) : (
            <View className="h-4" />
          )}
        </View>

        {/* Slab decision */}
        {slab && (
          <>
            <SectionTitle>Should you slab it?</SectionTitle>
            <View className="rounded-3xl bg-ink-900 border p-4" style={{ borderColor: VERDICT[slab.verdict].color }}>
              <View className="flex-row items-center justify-between mb-2">
                <Pill label={VERDICT[slab.verdict].label} color={VERDICT[slab.verdict].color} solid />
                <Text className="text-neutral-400 text-xs">about {slab.turnaround_days} business days</Text>
              </View>
              <Row label="Raw value today" value={usd(slab.raw_value)} />
              <Row label={`Slabbed at ${report!.grade.toFixed(1)}`} value={usd(slab.slabbed_value)} />
              <Row label="Grading fee + shipping" value={`-${usd(slab.grading_fee + slab.shipping)}`} tone={colors.muted} />
              <View className="h-px bg-ink-800 my-1" />
              <Row
                label="Net uplift"
                value={`${slab.net_uplift >= 0 ? '+' : '-'}${usd(Math.abs(slab.net_uplift))}`}
                tone={slab.net_uplift >= 0 ? colors.green : colors.red}
              />
            </View>
          </>
        )}

        {/* Price history */}
        <SectionTitle>Recorded sales</SectionTitle>
        {prices.length === 0 ? (
          <Text className="text-neutral-400">No recorded sales yet.</Text>
        ) : (
          [...prices]
            .reverse()
            .slice(0, 5)
            .map((p, i) => (
              <View key={i} className="flex-row items-center justify-between rounded-xl bg-ink-900 px-4 py-3 mb-2">
                <Text className="text-neutral-300 text-sm">{p.sale_date}</Text>
                <Text className="text-neutral-500 text-xs">{p.source}</Text>
                <Text className="text-pop-cyan font-bold">{usd(p.price, true)}</Text>
              </View>
            ))
        )}

        <View className="flex-row gap-2 mt-2">
          <TextInput
            value={priceInput}
            onChangeText={setPriceInput}
            placeholder="Add a sale price (e.g. 249.99)"
            placeholderTextColor="#6b6b80"
            keyboardType="decimal-pad"
            className="flex-1 rounded-2xl bg-ink-900 border border-ink-800 px-4 py-3 text-white"
          />
          <Button label="Log" onPress={addPrice} />
        </View>
      </ScrollView>
      <Toast message={toast} onDone={clearToast} />
    </View>
  );
}
