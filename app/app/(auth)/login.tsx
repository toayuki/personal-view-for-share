import { Link, router, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { StyleSheet, Text, TextInput, TouchableOpacity, View } from 'react-native';

import { useColorScheme } from '@/hooks/use-color-scheme';

export default function LoginScreen() {
  const { invite } = useLocalSearchParams<{ invite?: string }>();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [errorMsg, setErrorMsg] = useState('');
  const scheme = useColorScheme();
  const colors = scheme === 'dark'
    ? { bg: '#121212', text: '#fff', input: '#1e1e1e', border: '#444' }
    : { bg: '#fff', text: '#000', input: '#fff', border: '#ccc' };

  const handleSubmit = async () => {
    setErrorMsg('');
    try {
      const body = new URLSearchParams({ username, password });
      if (invite) body.append('invite', invite);

      const res = await fetch('/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: body.toString(),
      });

      if (res.ok) {
        router.replace('/(main)');
      } else {
        const data = await res.json().catch(() => ({}));
        setErrorMsg(data.error_msg ?? 'ログインに失敗しました');
      }
    } catch {
      setErrorMsg('通信エラーが発生しました');
    }
  };

  return (
    <View style={[styles.container, { backgroundColor: colors.bg }]}>
      <View style={styles.box}>
        <Text style={[styles.title, { color: colors.text }]}>Personal Web</Text>

        <Text style={[styles.label, { color: colors.text }]}>Username or Email</Text>
        <TextInput
          style={[styles.input, { backgroundColor: colors.input, borderColor: colors.border, color: colors.text }]}
          value={username}
          onChangeText={setUsername}
          autoCapitalize="none"
          autoComplete="username"
          keyboardType="email-address"
          placeholderTextColor={colors.border}
          autoFocus
        />

        <Text style={[styles.label, { color: colors.text }]}>Password</Text>
        <TextInput
          style={[styles.input, { backgroundColor: colors.input, borderColor: colors.border, color: colors.text }]}
          value={password}
          onChangeText={setPassword}
          secureTextEntry
          autoComplete="current-password"
          placeholderTextColor={colors.border}
        />

        {errorMsg ? <Text style={styles.error}>{errorMsg}</Text> : null}

        <TouchableOpacity style={styles.button} onPress={handleSubmit}>
          <Text style={styles.buttonText}>Enter</Text>
        </TouchableOpacity>

        <Link href="/(auth)/signup" style={styles.subLink}>
          <Text style={[styles.subLinkText, { color: colors.text }]}>新規会員登録</Text>
        </Link>
        <Link href="/(auth)/forgot-password" style={styles.subLink}>
          <Text style={[styles.subLinkText, { color: colors.text }]}>パスワードを忘れた場合</Text>
        </Link>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 24,
  },
  box: {
    width: '100%',
    maxWidth: 360,
    gap: 12,
  },
  title: {
    fontSize: 32,
    fontWeight: 'bold',
    textAlign: 'center',
    marginBottom: 8,
  },
  label: {
    fontSize: 14,
    marginBottom: -4,
  },
  input: {
    borderWidth: 1,
    borderColor: '#ccc',
    borderRadius: 8,
    padding: 12,
    fontSize: 16,
  },
  error: {
    color: '#e53e3e',
    fontSize: 14,
  },
  button: {
    backgroundColor: '#333',
    borderRadius: 8,
    padding: 14,
    alignItems: 'center',
    marginTop: 4,
  },
  buttonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
  },
  subLink: {
    alignSelf: 'center',
  },
  subLinkText: {
    fontSize: 14,
    textDecorationLine: 'underline',
  },
});
