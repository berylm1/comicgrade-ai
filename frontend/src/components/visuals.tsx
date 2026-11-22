/** SVG visuals: generated placeholder covers, value charts and the grade dial. */
import React from 'react';
import { Image, Text, View } from 'react-native';
import Svg, { Circle, Defs, LinearGradient, Path, Polygon, Rect, Stop, Text as SvgText } from 'react-native-svg';

import type { Comic, DefectScore } from '../types';
import { seeded } from '../lib/grading';
import { colors, gradeColor } from './ui';

const DISPLAY_FONT = 'Anton_400Regular';

type CoverComic = Pick<Comic, 'title' | 'issue_number' | 'publisher' | 'cover_image_url' | 'cover_palette'>;

function wrapTitle(title: string): string[] {
  const lines: string[] = [];
  title
    .toUpperCase()
    .split(' ')
    .forEach((word) => {
      const last = lines[lines.length - 1];
      if (last && (last + ' ' + word).length <= 11) lines[lines.length - 1] = `${last} ${word}`;
      else lines.push(word);
    });
  return lines.slice(0, 4);
}

function burst(cx: number, cy: number, outer: number, inner: number, points: number): string {
  return Array.from({ length: points * 2 }, (_, i) => {
    const r = i % 2 === 0 ? outer : inner;
    const a = (Math.PI * i) / points - Math.PI / 2;
    return `${(cx + r * Math.cos(a)).toFixed(1)},${(cy + r * Math.sin(a)).toFixed(1)}`;
  }).join(' ');
}

/**
 * Cover image when one exists, otherwise an original generated placeholder
 * (never real cover art) drawn from the book's palette.
 */
export function CoverArt({ comic, width }: { comic: CoverComic; width: number }) {
  const height = width * 1.5;
  if (comic.cover_image_url) {
    return <Image source={{ uri: comic.cover_image_url }} style={{ width, height, borderRadius: width * 0.04 }} />;
  }
  const key = `${comic.title}#${comic.issue_number}`;
  const rng = seeded(key);
  const [from, to, accent] = comic.cover_palette ?? ['#2f6bff', '#12121f', '#ffd21f'];
  const id = key.replace(/[^a-z0-9]/gi, '');
  const lines = wrapTitle(comic.title);
  const longest = Math.max(...lines.map((l) => l.length));
  const fontSize = Math.min(17, 86 / (longest * 0.52));
  const bx = 30 + rng() * 40;
  const by = 86 + rng() * 22;
  const dots = [];
  for (let row = 0; row < 9; row++) {
    for (let col = 0; col < 11; col++) {
      dots.push(
        <Circle key={`${row}-${col}`} cx={5 + col * 9 + (row % 2) * 4.5} cy={78 + row * 8} r={0.5 + row * 0.32} fill={accent} opacity={0.2} />,
      );
    }
  }
  return (
    <Svg width={width} height={height} viewBox="0 0 100 150">
      <Defs>
        <LinearGradient id={`bg${id}`} x1="0" y1="0" x2="1" y2="1">
          <Stop offset="0" stopColor={from} />
          <Stop offset="1" stopColor={to} />
        </LinearGradient>
      </Defs>
      <Rect width="100" height="150" rx="4" fill={`url(#bg${id})`} />
      {dots}
      <Polygon points={burst(bx, by, 30, 17, 11)} fill={accent} opacity={0.92} />
      <Polygon points={burst(bx, by, 17, 9, 9)} fill={to} opacity={0.55} />
      <Rect x="5" y="5" width="15" height="21" rx="1.5" fill="#fff" />
      <SvgText x="12.5" y="13" fontSize="3.4" fontWeight="bold" textAnchor="middle" fill="#111">
        {comic.publisher.slice(0, 6).toUpperCase()}
      </SvgText>
      <SvgText x="12.5" y="22" fontSize="7" fontFamily={DISPLAY_FONT} textAnchor="middle" fill="#111">
        {comic.issue_number}
      </SvgText>
      {lines.map((line, i) => (
        <SvgText
          key={i}
          x="24"
          y={17 + i * (fontSize + 1)}
          fontSize={fontSize}
          fontFamily={DISPLAY_FONT}
          fill="#fff"
          stroke="#000"
          strokeWidth="0.35"
        >
          {line}
        </SvgText>
      ))}
      <Rect x="0.75" y="0.75" width="98.5" height="148.5" rx="3.5" fill="none" stroke="#000" strokeOpacity="0.35" strokeWidth="1.5" />
    </Svg>
  );
}

/** Filled line chart of a value series. */
export function AreaChart({
  points,
  width,
  height,
  color = colors.cyan,
}: {
  points: number[];
  width: number;
  height: number;
  color?: string;
}) {
  if (points.length < 2 || width <= 0) return <View style={{ width, height }} />;
  const min = Math.min(...points);
  const max = Math.max(...points);
  const span = max - min || 1;
  const pad = 6;
  const xy = points.map((p, i) => [
    (i / (points.length - 1)) * (width - pad * 2) + pad,
    height - pad - ((p - min) / span) * (height - pad * 2),
  ]);
  const line = xy.map(([x, y], i) => `${i ? 'L' : 'M'}${x.toFixed(1)} ${y.toFixed(1)}`).join(' ');
  const [lx, ly] = xy[xy.length - 1];
  const gid = `area${color.replace('#', '')}`;
  return (
    <Svg width={width} height={height}>
      <Defs>
        <LinearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
          <Stop offset="0" stopColor={color} stopOpacity="0.35" />
          <Stop offset="1" stopColor={color} stopOpacity="0" />
        </LinearGradient>
      </Defs>
      <Path d={`${line} L${lx} ${height} L${xy[0][0]} ${height} Z`} fill={`url(#${gid})`} />
      <Path d={line} stroke={color} strokeWidth={2.5} fill="none" strokeLinejoin="round" strokeLinecap="round" />
      <Circle cx={lx} cy={ly} r={4.5} fill={color} stroke={colors.ink900} strokeWidth={2} />
    </Svg>
  );
}

/** Circular dial showing the grade on the 10-point scale. */
export function GradeDial({ grade, size = 112 }: { grade: number; size?: number }) {
  const stroke = 9;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const tone = gradeColor(grade);
  return (
    <View style={{ width: size, height: size }} className="items-center justify-center">
      <Svg width={size} height={size} style={{ position: 'absolute' }}>
        <Circle cx={size / 2} cy={size / 2} r={r} stroke={colors.ink800} strokeWidth={stroke} fill="none" />
        <Circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          stroke={tone}
          strokeWidth={stroke}
          strokeLinecap="round"
          fill="none"
          strokeDasharray={`${(grade / 10) * c} ${c}`}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
      </Svg>
      <Text className="font-display text-4xl" style={{ color: tone }}>
        {grade.toFixed(1)}
      </Text>
    </View>
  );
}

export function DefectBar({ defect }: { defect: DefectScore }) {
  const tone = gradeColor(defect.score);
  return (
    <View className="mb-3">
      <View className="flex-row justify-between mb-1">
        <Text className="text-white text-xs font-bold">{defect.area}</Text>
        <Text className="text-xs font-bold" style={{ color: tone }}>
          {defect.score.toFixed(1)}
        </Text>
      </View>
      <View className="h-1.5 rounded-full bg-ink-800 overflow-hidden">
        <View className="h-full rounded-full" style={{ width: `${defect.score * 10}%`, backgroundColor: tone }} />
      </View>
      <Text className="text-neutral-400 text-[11px] mt-1">{defect.note}</Text>
    </View>
  );
}

export function ProgressBar({ value, color = colors.cyan }: { value: number; color?: string }) {
  return (
    <View className="h-2 rounded-full bg-ink-800 overflow-hidden">
      <View className="h-full rounded-full" style={{ width: `${Math.round(value * 100)}%`, backgroundColor: color }} />
    </View>
  );
}
