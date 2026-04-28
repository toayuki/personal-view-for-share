import { Link } from 'expo-router';
import { StyleSheet, Text, View } from 'react-native';

import { useColorScheme } from '@/hooks/use-color-scheme';

export default function HomeScreen() {
  const scheme = useColorScheme();
  const colors = scheme === 'dark'
    ? { bg: '#121212', text: '#fff' }
    : { bg: '#fff', text: '#000' };

  return (
    <View style={[styles.container, { backgroundColor: colors.bg }]}>
      <Text style={[styles.title, { color: colors.text }]}>Home</Text>
      <Link href="/(auth)/login">
        <Text style={{ color: colors.text }}>Login</Text>
      </Link>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  title: {
    fontSize: 32,
    fontWeight: 'bold',
  },
});
