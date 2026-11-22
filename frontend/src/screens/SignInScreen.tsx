import React, { useState } from 'react';
import { KeyboardAvoidingView, Platform, Text, TextInput, View } from 'react-native';

import { useAuth } from '../lib/auth';
import { Button, colors, LoadingDots } from '../components/ui';

type Step = 'email' | 'code';

/** Email sign-in with a one-time code (no password, no deep links needed). */
export default function SignInScreen() {
  const { sendCode, verifyCode } = useAuth();
  const [step, setStep] = useState<Step>('email');
  const [email, setEmail] = useState('');
  const [code, setCode] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const validEmail = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());

  const run = async (action: () => Promise<void>) => {
    setBusy(true);
    setError(null);
    try {
      await action();
    } catch (err: any) {
      setError(err?.message ?? 'Something went wrong. Try again.');
    } finally {
      setBusy(false);
    }
  };

  const onSend = () =>
    run(async () => {
      await sendCode(email);
      setStep('code');
    });

  const onVerify = () => run(() => verifyCode(email, code));

  const inputStyle = {
    borderColor: colors.ink800,
    color: '#f5f5fa',
  };

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      className="flex-1 bg-ink-950 justify-center px-6"
    >
      <Text className="text-pop-magenta text-xs font-bold uppercase tracking-widest">ComicGrade AI</Text>
      <Text className="text-white text-4xl font-display uppercase mt-1">Sign in</Text>
      <Text className="text-neutral-400 mt-2">
        {step === 'email'
          ? 'Enter your email and we will send you a sign-in code. No password needed.'
          : `We sent a code to ${email.trim()}. Enter it below.`}
      </Text>

      {step === 'email' ? (
        <TextInput
          value={email}
          onChangeText={setEmail}
          placeholder="you@example.com"
          placeholderTextColor={colors.muted}
          autoCapitalize="none"
          autoComplete="email"
          keyboardType="email-address"
          accessibilityLabel="Email address"
          onSubmitEditing={validEmail ? onSend : undefined}
          className="mt-6 rounded-2xl border bg-ink-900 px-4 py-3 text-base"
          style={inputStyle}
        />
      ) : (
        <TextInput
          value={code}
          onChangeText={(t) => setCode(t.replace(/\D/g, ''))}
          placeholder="Code"
          placeholderTextColor={colors.muted}
          keyboardType="number-pad"
          autoComplete="one-time-code"
          maxLength={10}
          accessibilityLabel="Sign-in code"
          onSubmitEditing={code.length >= 6 ? onVerify : undefined}
          className="mt-6 rounded-2xl border bg-ink-900 px-4 py-3 text-2xl tracking-widest"
          style={inputStyle}
        />
      )}

      {error ? <Text className="text-pop-red mt-3">{error}</Text> : null}

      <View className="mt-6 gap-3">
        {busy ? (
          <LoadingDots label={step === 'email' ? 'Sending code...' : 'Signing in...'} />
        ) : step === 'email' ? (
          <Button label="Send code" onPress={onSend} disabled={!validEmail} />
        ) : (
          <>
            <Button label="Sign in" onPress={onVerify} disabled={code.length < 6} />
            <Button
              label="Use a different email"
              tone="ghost"
              onPress={() => {
                setStep('email');
                setCode('');
                setError(null);
              }}
            />
          </>
        )}
      </View>
    </KeyboardAvoidingView>
  );
}
