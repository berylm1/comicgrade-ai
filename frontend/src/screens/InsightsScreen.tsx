import React, { useCallback, useState } from 'react';
import { Pressable, ScrollView, Text, View } from 'react-native';
import { useFocusEffect } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';

import { api } from '../lib/api';
import type { Comic, GradeReport, RunGap } from '../types';
import { Button, colors, isRaw, Pill, SectionTitle, Toast, usd } from '../components/ui';
import { CoverArt, ProgressBar } from '../components/visuals';

type Props = { navigation: NativeStackNavigationProp<any> };
type Candidate = { comic: Comic; report: GradeReport };

/** Pre-screen queue, run gaps and the insurance export. */
export default function InsightsScreen({ navigation }: Props) {
  const [comics, setComics] = useState<Comic[]>([]);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [runs, setRuns] = useState<RunGap[]>([]);
  const [toast, setToast] = useState<string | null>(null);
  const clearToast = useCallback(() => setToast(null), []);

  useFocusEffect(
    useCallback(() => {
      let live = true;
      (async () => {
        const [list, gaps] = await Promise.all([api.listComics(), api.listRunGaps()]);
        const reports = await Promise.all(
          list.filter((c) => isRaw(c.grade_type)).map(async (comic) => ({ comic, report: await api.getGradeReport(comic.id) })),
        );
        if (!live) return;
        setComics(list);
        setRuns(gaps);
        setCandidates(
          reports
            .filter((x): x is Candidate => x.report?.slab?.verdict === 'submit')
            .sort((a, b) => (b.report.slab?.net_uplift ?? 0) - (a.report.slab?.net_uplift ?? 0)),
        );
      })().catch((err) => live && setToast(err?.message ?? 'Failed to load insights'));
      return () => {
        live = false;
      };
    }, []),
  );

  const totalUplift = candidates.reduce((s, c) => s + (c.report.slab?.net_uplift ?? 0), 0);
  const totalValue = comics.reduce((s, c) => s + (c.current_market_value ?? 0), 0);
  const today = new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });

  return (
    <View className="flex-1 bg-ink-950">
      <ScrollView contentContainerStyle={{ padding: 20, paddingTop: 56, paddingBottom: 40 }}>
        <Text className="text-white text-4xl font-display uppercase">Insights</Text>
        <Text className="text-neutral-400">Know what to grade, what to chase and what it is all worth.</Text>

        {/* Submission pre-screen */}
        <SectionTitle>Worth slabbing</SectionTitle>
        <View className="rounded-3xl border border-pop-yellow p-4" style={{ backgroundColor: '#ffd21f14' }}>
          <Text className="text-[10px] uppercase tracking-widest text-neutral-300">Potential uplift after fees</Text>
          <Text className="text-pop-yellow text-4xl font-display mt-1">+{usd(totalUplift)}</Text>
          <Text className="text-neutral-300 text-xs mt-1">
            {candidates.length} of your raw books clear grading and shipping costs at their likely grade.
          </Text>
        </View>
        {candidates.map(({ comic, report }) => (
          <Pressable
            key={comic.id}
            onPress={() => navigation.navigate('ComicDetail', { comicId: comic.id })}
            className="flex-row items-center rounded-2xl bg-ink-900 border border-ink-800 p-3 mt-2"
          >
            <CoverArt comic={comic} width={44} />
            <View className="flex-1 ml-3">
              <Text className="text-white font-bold" numberOfLines={1}>
                {comic.title} #{comic.issue_number}
              </Text>
              <Text className="text-neutral-400 text-xs mt-0.5">
                Likely {report.grade_low.toFixed(1)} to {report.grade_high.toFixed(1)}
              </Text>
              <Text className="text-neutral-300 text-xs mt-0.5">
                {usd(report.slab!.raw_value)} raw → {usd(report.slab!.slabbed_value)} slabbed
              </Text>
            </View>
            <View className="items-end">
              <Text className="text-grade-high font-display text-xl">+{usd(report.slab!.net_uplift)}</Text>
              <Text className="text-neutral-500 text-[10px]">net of fees</Text>
            </View>
          </Pressable>
        ))}
        {candidates.length === 0 && (
          <Text className="text-neutral-400 mt-3">No raw books currently clear the cost of grading.</Text>
        )}

        {/* Run gaps */}
        {runs.length > 0 && <SectionTitle>Finish your runs</SectionTitle>}
        {runs.map((run) => (
          <View key={run.id} className="rounded-2xl bg-ink-900 border border-ink-800 p-4 mb-2">
            <View className="flex-row items-end justify-between mb-2">
              <Text className="text-white font-bold flex-1 mr-2" numberOfLines={1}>
                {run.name}
              </Text>
              <Text className="text-pop-cyan font-display text-lg">
                {run.owned}/{run.total}
              </Text>
            </View>
            <ProgressBar value={run.owned / run.total} />
            <View className="flex-row items-center mt-3">
              <Pill label={`Missing ${run.missing_key}`} color={colors.magenta} />
              <Text className="text-neutral-400 text-xs ml-2 flex-1" numberOfLines={1}>
                {run.missing_note}
              </Text>
            </View>
            <Text className="text-neutral-300 text-xs mt-2">
              About <Text className="text-white font-bold">{usd(run.raw_price)}</Text> raw or{' '}
              <Text className="text-white font-bold">{usd(run.slab_price)}</Text> slabbed 9.8
            </Text>
          </View>
        ))}

        {/* Insurance / export */}
        <SectionTitle>Insurance and export</SectionTitle>
        <View className="rounded-3xl bg-ink-900 border border-ink-800 p-4">
          <Text className="text-[10px] uppercase tracking-widest text-neutral-400">Appraised total · {today}</Text>
          <Text className="text-white text-3xl font-display mt-1">{usd(totalValue)}</Text>
          <Text className="text-neutral-400 text-xs mt-1">
            {comics.length} itemized books with grade, photos and dated valuation. Your data is always yours to take.
          </Text>
          <View className="flex-row gap-2 mt-4">
            <View className="flex-1">
              <Button label="Appraisal PDF" onPress={() => setToast(`Appraisal ready: ${comics.length} books, ${usd(totalValue)} (demo)`)} />
            </View>
            <Button label="CSV" tone="ghost" onPress={() => setToast('CSV export ready (demo)')} />
            <Button label="JSON" tone="ghost" onPress={() => setToast('JSON export ready (demo)')} />
          </View>
        </View>
      </ScrollView>
      <Toast message={toast} onDone={clearToast} />
    </View>
  );
}
