import './global.css';

import React from 'react';
import { ActivityIndicator, View, useWindowDimensions } from 'react-native';
import { StatusBar } from 'expo-status-bar';
import { useFonts } from 'expo-font';
import { Anton_400Regular } from '@expo-google-fonts/anton';
import { Ionicons } from '@expo/vector-icons';
import { NavigationContainer, DarkTheme } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';

import DashboardScreen from './src/screens/DashboardScreen';
import CollectionScreen from './src/screens/CollectionScreen';
import ScanScreen from './src/screens/ScanScreen';
import InsightsScreen from './src/screens/InsightsScreen';
import ComicDetailScreen from './src/screens/ComicDetailScreen';
import SignInScreen from './src/screens/SignInScreen';
import { AUTH_ENABLED, AuthProvider, useAuth } from './src/lib/auth';
import { FRAME_HEIGHT, FRAME_WIDTH, useFramed } from './src/components/ui';

type RootStackParamList = {
  Tabs: undefined;
  ComicDetail: { comicId: string };
};

const Stack = createNativeStackNavigator<RootStackParamList>();
const Tab = createBottomTabNavigator();

const ICONS: Record<string, keyof typeof Ionicons.glyphMap> = {
  Vault: 'wallet',
  Collection: 'albums',
  Scan: 'scan-circle',
  Insights: 'sparkles',
};

function Tabs() {
  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        headerShown: false,
        tabBarStyle: {
          backgroundColor: '#12121f',
          borderTopColor: '#1c1c2e',
          height: 68,
          paddingBottom: 8,
          paddingTop: 6,
        },
        tabBarActiveTintColor: '#ffd21f',
        tabBarInactiveTintColor: '#6b6b80',
        tabBarLabelStyle: { fontWeight: '700', fontSize: 11 },
        tabBarIcon: ({ color, focused }) => (
          <Ionicons
            name={focused ? ICONS[route.name] : (`${ICONS[route.name]}-outline` as keyof typeof Ionicons.glyphMap)}
            size={route.name === 'Scan' ? 28 : 22}
            color={color}
          />
        ),
      })}
    >
      <Tab.Screen name="Vault" component={DashboardScreen} />
      <Tab.Screen name="Collection" component={CollectionScreen} />
      <Tab.Screen name="Scan" component={ScanScreen} />
      <Tab.Screen name="Insights" component={InsightsScreen} />
    </Tab.Navigator>
  );
}

/** On a desktop browser, present the app inside a phone-sized frame. */
function DeviceFrame({ children }: { children: React.ReactNode }) {
  const framed = useFramed();
  const { height } = useWindowDimensions();
  if (!framed) return <View style={{ flex: 1, backgroundColor: '#0a0a12' }}>{children}</View>;
  return (
    <View style={{ flex: 1, backgroundColor: '#04040a', alignItems: 'center', justifyContent: 'center' }}>
      <View
        style={{
          width: FRAME_WIDTH,
          height: Math.min(height - 24, FRAME_HEIGHT),
          borderRadius: 40,
          borderWidth: 4,
          borderColor: '#2a2a40',
          overflow: 'hidden',
          backgroundColor: '#0a0a12',
        }}
      >
        {children}
      </View>
    </View>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppShell />
    </AuthProvider>
  );
}

function AppShell() {
  const [fontsLoaded] = useFonts({ Anton_400Regular, ...Ionicons.font });
  const { session, loading } = useAuth();

  return (
    <DeviceFrame>
      <StatusBar style="light" />
      {!fontsLoaded || loading ? (
        <ActivityIndicator color="#ffd21f" style={{ marginTop: 160 }} />
      ) : AUTH_ENABLED && !session ? (
        <SignInScreen />
      ) : (
        <NavigationContainer
          theme={{
            ...DarkTheme,
            colors: {
              ...DarkTheme.colors,
              background: '#0a0a12',
              card: '#12121f',
              primary: '#ffd21f',
              text: '#f5f5fa',
              border: '#1c1c2e',
              notification: '#ff3b3b',
            },
          }}
        >
          <Stack.Navigator
            screenOptions={{
              headerStyle: { backgroundColor: '#0a0a12' },
              headerTintColor: '#ffd21f',
              headerShadowVisible: false,
            }}
          >
            <Stack.Screen name="Tabs" component={Tabs} options={{ headerShown: false, title: 'ComicGrade AI' }} />
            <Stack.Screen
              name="ComicDetail"
              component={ComicDetailScreen}
              options={{ title: 'Comic', headerTitle: '', headerBackTitle: 'Back' }}
            />
          </Stack.Navigator>
        </NavigationContainer>
      )}
    </DeviceFrame>
  );
}
