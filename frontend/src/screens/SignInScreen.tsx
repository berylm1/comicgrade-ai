import React, { useState } from 'react';
import { KeyboardAvoidingView, Platform, Text, TextInput, View } from 'react-native';

import { useAuth } from '../lib/auth';
import { Button, colors, LoadingDots } from '../components/ui';

/**
 * password: email + password (works with Supabase's default email settings).
 * code-email / code-verify: one-time email code. Needs custom SMTP and a Magic
 * Link template containing {{ .Token }} in the Supabase project.
 */
type Mode = 'password' | 'code-email' | 'code-verify';

const MIN_PASSWORD = 8;

export default function SignInScreen() {
  const { signInWithPassword, signUp, sendCode, verifyCode } = useAuth();
  const [mode, setMode] = useState<Mode>('password');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [code, setCode] = useState('');
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  const validEmail = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());

  const run = async (label: string, action: () => Promise<void>) => {
    setBusy(label);
    setError(null);
    setInfo(null);
    try {
      await action();
    } catch (err: any) {
      setError(friendly(err?.message));
    } finally {
      setBusy(null);
    }
  };

  const onSignIn = () => run('Signing in...', () => signInWithPassword(email, password));

  const onCreate = () =>
    run('Creating account...', async () => {
      const signedIn = await signUp(email, password);
      if (!signedIn) {
        setInfo(
          `Check ${email.trim()} for a confirmation email and open the link. ` +
            'Then come back and sign in. (The page the link opens may not load; the account is confirmed anyway.)',
        );
      }
    });

  const onSendCode = () =>
    run('Sending code...', async () => {
      await sendCode(email);
      setMode('code-verify');
    });

  const onVerify = () => run('Signing in...', () => verifyCode(email, code));

  const switchMode = (next: Mode) => {
    setMode(next);
    setError(null);
    setInfo(null);
    setCode('');
  };

  const input = 'mt-3 rounded-2xl border bg-ink-900 px-4 py-3 text-base';
  const inputStyle = { borderColor: colors.ink800, color: '#f5f5fa' };

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      className="flex-1 bg-ink-950 justify-center px-6"
    >
      <Text className="text-pop-magenta text-xs font-bold uppercase tracking-widest">ComicGrade AI</Text>
      <Text className="text-white text-4xl font-display uppercase mt-1">Sign in</Text>
      <Text className="text-neutral-400 mt-2">
        {mode === 'password'
          ? 'Sign in, or create an account with your email and a password.'
          : mode === 'code-email'
            ? 'We will email you a one-time sign-in code.'
            : `We sent a code to ${email.trim()}. Enter it below.`}
      </Text>

      {mode !== 'code-verify' && (
        <TextInput
          value={email}
          onChangeText={setEmail}
          placeholder="you@example.com"
          placeholderTextColor={colors.muted}
          autoCapitalize="none"
          autoComplete="email"
          keyboardType="email-address"
          accessibilityLabel="Email address"
          className={`${input} mt-6`}
          style={inputStyle}
        />
      )}

      {mode === 'password' && (
        <TextInput
          value={password}
          onChangeText={setPassword}
          placeholder={`Password (at least ${MIN_PASSWORD} characters)`}
          placeholderTextColor={colors.muted}
          secureTextEntry
          autoCapitalize="none"
          autoComplete="password"
          accessibilityLabel="Password"
          onSubmitEditing={validEmail && password ? onSignIn : undefined}
          className={input}
          style={inputStyle}
        />
      )}

      {mode === 'code-verify' && (
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
          className={`${input} mt-6 text-2xl tracking-widest`}
          style={inputStyle}
        />
      )}

      {error ? <Text className="text-pop-red mt-3">{error}</Text> : null}
      {info ? <Text className="text-pop-cyan mt-3">{info}</Text> : null}

      <View className="mt-6 gap-3">
        {busy ? (
          <LoadingDots label={busy} />
        ) : mode === 'password' ? (
          <>
            <Button label="Sign in" onPress={onSignIn} disabled={!validEmail || !password} />
            <Button
              label="Create account"
              tone="ghost"
              onPress={onCreate}
              disabled={!validEmail || password.length < MIN_PASSWORD}
            />
            <Text className="text-neutral-400 text-center mt-2" onPress={() => switchMode('code-email')}>
              Email me a sign-in code instead
            </Text>
          </>
        ) : mode === 'code-email' ? (
          <>
            <Button label="Send code" onPress={onSendCode} disabled={!validEmail} />
            <Text className="text-neutral-400 text-center mt-2" onPress={() => switchMode('password')}>
              Use a password instead
            </Text>
          </>
        ) : (
          <>
            <Button label="Sign in" onPress={onVerify} disabled={code.length < 6} />
            <Button label="Use a different email" tone="ghost" onPress={() => switchMode('code-email')} />
          </>
        )}
      </View>
    </KeyboardAvoidingView>
  );
}

/** Plain-language versions of the common Supabase auth errors. */
function friendly(message?: string): string {
  const m = (message ?? '').toLowerCase();
  if (m.includes('invalid login credentials')) return 'That email and password do not match an account.';
  if (m.includes('email not confirmed')) return 'Confirm your email first: open the link we sent, then sign in.';
  if (m.includes('already registered')) return 'An account with this email already exists. Sign in instead.';
  if (m.includes('rate limit')) return 'Too many emails sent recently. Wait a while and try again.';
  if (m.includes('password')) return message ?? 'Choose a stronger password.';
  return message || 'Something went wrong. Try again.';
}
