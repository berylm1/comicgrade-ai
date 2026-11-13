import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Animated, Easing, Pressable, Text, View } from 'react-native';
import { useFocusEffect } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';

import { api } from '../lib/api';
import { DEMO_MODE } from '../lib/env';
import type { ScanMatch } from '../types';
import { Button, colors, Pill, usd, useAppWidth } from '../components/ui';
import { CoverArt, GradeDial } from '../components/visuals';
import LiveScanner from './LiveScanner';

type Props = { navigation: NativeStackNavigationProp<any> };
type Phase = 'frame' | 'analyzing' | 'result' | 'saving';

const STEPS = [
  { label: 'Front', hint: 'Center the front cover in the frame' },
  { label: 'Back', hint: 'Flip the book and frame the back cover' },
  { label: 'Spine', hint: 'Turn the book so the spine faces the camera' },
];
const ANALYSIS = ['Identifying cover…', 'Mapping corners, spine and surface…', 'Pulling recent sales…'];

function Bracket({ pos }: { pos: 'tl' | 'tr' | 'bl' | 'br' }) {
  const top = pos[0] === 't';
  const left = pos[1] === 'l';
  return (
    <View
      style={{
        position: 'absolute',
        width: 34,
        height: 34,
        borderColor: colors.yellow,
        [top ? 'top' : 'bottom']: 0,
        [left ? 'left' : 'right']: 0,
        [top ? 'borderTopWidth' : 'borderBottomWidth']: 4,
        [left ? 'borderLeftWidth' : 'borderRightWidth']: 4,
        [`border${top ? 'Top' : 'Bottom'}${left ? 'Left' : 'Right'}Radius`]: 18,
      }}
    />
  );
}

/**
 * Guided scan walkthrough on sample books: three framed captures, then the
 * identification, explainable grade and value. Stands in for the camera so the
 * flow can be shown in a browser or simulator.
 */
function DemoScanner({ navigation }: Props) {
  const width = useAppWidth();
  const [match, setMatch] = useState<ScanMatch>(() => api.peekScan());
  const [phase, setPhase] = useState<Phase>('frame');
  const [step, setStep] = useState(0);
  const [message, setMessage] = useState(0);
  // Height left for the viewfinder once the header and controls are laid out.
  const [space, setSpace] = useState(0);
  const flash = useRef(new Animated.Value(0)).current;
  const sweep = useRef(new Animated.Value(0)).current;

  const reset = useCallback(() => {
    setMatch(api.peekScan());
    setPhase('frame');
    setStep(0);
    setMessage(0);
  }, []);

  // A fresh sample each time the tab is opened.
  useFocusEffect(reset);

  useEffect(() => {
    if (phase !== 'analyzing') return;
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(sweep, { toValue: 1, duration: 900, easing: Easing.inOut(Easing.quad), useNativeDriver: true }),
        Animated.timing(sweep, { toValue: 0, duration: 900, easing: Easing.inOut(Easing.quad), useNativeDriver: true }),
      ]),
    );
    loop.start();
    const ticks = ANALYSIS.map((_, i) => setTimeout(() => setMessage(i), i * 1000));
    const done = setTimeout(() => setPhase('result'), ANALYSIS.length * 1000);
    return () => {
      loop.stop();
      ticks.forEach(clearTimeout);
      clearTimeout(done);
    };
  }, [phase, sweep]);

  const capture = () => {
    flash.setValue(0.85);
    Animated.timing(flash, { toValue: 0, duration: 320, useNativeDriver: true }).start();
    if (step < STEPS.length - 1) setStep(step + 1);
    else setPhase('analyzing');
  };

  const addToVault = async () => {
    setPhase('saving');
    const comic = await api.commitScan(match);
    navigation.navigate('ComicDetail', { comicId: comic.id });
  };

  const frameW = Math.max(90, Math.min(width * 0.6, 250, space ? (space - 24) / 1.5 : 250));
  const frameH = frameW * 1.5;
  const coverW = frameW - 28;
  const framing = phase === 'frame';
  const { comic, report } = match;

  return (
    <View className="flex-1 bg-ink-950 pt-14">
      <View className="px-5 flex-row items-center justify-between">
        <Text className="text-white text-4xl font-display uppercase">Scan</Text>
        <Pill label="Sample book" color={colors.magenta} />
      </View>

      {/* Guided capture steps */}
      <View className="flex-row gap-2 px-5 mt-3">
        {STEPS.map(({ label }, i) => {
          const done = !framing || i < step;
          const current = framing && i === step;
          return (
            <View
              key={label}
              className="flex-1 rounded-full py-1.5 items-center border"
              style={{
                borderColor: done ? colors.green : current ? colors.yellow : colors.ink800,
                backgroundColor: done ? '#3ddc8422' : colors.ink900,
              }}
            >
              <Text className="text-[11px] font-bold" style={{ color: done ? colors.green : current ? colors.yellow : colors.muted }}>
                {done ? '✓ ' : ''}
                {label}
              </Text>
            </View>
          );
        })}
      </View>

      {/* Viewfinder */}
      <View
        className="flex-1 items-center justify-center overflow-hidden"
        onLayout={(e) => setSpace(e.nativeEvent.layout.height)}
      >
        <View style={{ width: frameW, height: frameH }} className="items-center justify-center">
          <View
            style={{
              transform: [{ rotate: step === 1 && framing ? '2deg' : '-2deg' }, { scaleX: step === 1 && framing ? -1 : 1 }],
              opacity: step === 1 && framing ? 0.55 : 1,
              width: step === 2 && framing ? 26 : coverW,
              overflow: 'hidden',
            }}
          >
            <CoverArt comic={comic} width={coverW} />
          </View>
          <Bracket pos="tl" />
          <Bracket pos="tr" />
          <Bracket pos="bl" />
          <Bracket pos="br" />
          {phase === 'analyzing' && (
            <Animated.View
              style={{
                position: 'absolute',
                left: 6,
                right: 6,
                top: 0,
                height: 3,
                borderRadius: 2,
                backgroundColor: colors.cyan,
                shadowColor: colors.cyan,
                shadowOpacity: 0.9,
                shadowRadius: 12,
                transform: [{ translateY: sweep.interpolate({ inputRange: [0, 1], outputRange: [8, frameH - 12] }) }],
              }}
            />
          )}
          <Animated.View
            pointerEvents="none"
            style={{ position: 'absolute', top: 0, bottom: 0, left: 0, right: 0, backgroundColor: '#fff', borderRadius: 18, opacity: flash }}
          />
        </View>
      </View>

      {/* Controls / result */}
      {framing && (
        <View className="items-center pb-8">
          <Text className="text-neutral-300 text-sm mb-4 px-8 text-center">{STEPS[step].hint}</Text>
          <Pressable
            onPress={capture}
            accessibilityLabel="Capture"
            className="h-20 w-20 rounded-full border-4 border-pop-yellow items-center justify-center"
          >
            <View className="h-14 w-14 rounded-full bg-pop-red" />
          </Pressable>
        </View>
      )}

      {phase === 'analyzing' && (
        <View className="items-center pb-14">
          <Text className="text-pop-cyan font-bold">{ANALYSIS[message]}</Text>
          <Text className="text-neutral-500 text-xs mt-2">3 photos captured</Text>
        </View>
      )}

      {(phase === 'result' || phase === 'saving') && (
        <View className="mx-4 mb-5 rounded-3xl bg-ink-900 border border-pop-cyan p-4">
          <View className="flex-row items-center justify-between">
            <Pill label={`${Math.round(match.match_confidence * 100)}% match`} color={colors.green} />
            <Text className="text-neutral-400 text-xs">
              {comic.publisher} · {comic.year}
            </Text>
          </View>
          <View className="flex-row items-center mt-3">
            <GradeDial grade={report.grade} size={84} />
            <View className="flex-1 ml-4">
              <Text className="text-white text-xl font-display uppercase" numberOfLines={2}>
                {comic.title} #{comic.issue_number}
              </Text>
              <Text className="text-neutral-400 text-xs mt-1">
                Likely {report.grade_low.toFixed(1)} to {report.grade_high.toFixed(1)} · raw value{' '}
                <Text className="text-pop-yellow font-bold">{usd(comic.current_market_value)}</Text>
              </Text>
              {comic.key_note && <Text className="text-pop-magenta text-xs font-bold mt-1">{comic.key_note}</Text>}
            </View>
          </View>
          <View className="flex-row gap-2 mt-4">
            <View className="flex-1">
              <Button label={phase === 'saving' ? 'Adding…' : 'Add to vault'} onPress={addToVault} disabled={phase === 'saving'} />
            </View>
            <Button label="Rescan" tone="ghost" onPress={reset} />
          </View>
        </View>
      )}
    </View>
  );
}

export default function ScanScreen(props: Props) {
  return DEMO_MODE ? <DemoScanner {...props} /> : <LiveScanner />;
}
