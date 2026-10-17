import React from 'react';
import { StatusBar } from 'expo-status-bar';
import { NavigationContainer, DarkTheme } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { Text, View } from 'react-native';

import DashboardScreen from './src/screens/DashboardScreen';
import CollectionScreen from './src/screens/CollectionScreen';
import CameraScreen from './src/screens/CameraScreen';
import ComicDetailScreen from './src/screens/ComicDetailScreen';

type RootStackParamList = {
  Tabs: undefined;
  ComicDetail: { comicId: string };
};

const Stack = createNativeStackNavigator<RootStackParamList>();
const Tab = createBottomTabNavigator();

// Total tab order is camera-first: scan -> collection -> dashboard.
function TabIcon({ focused, glyph }: { focused: boolean; glyph: string }) {
  return (
    <View className="items-center justify-center">
      <Text style={{ fontSize: 20, opacity: focused ? 1 : 0.45 }}>{glyph}</Text>
    </View>
  );
}

function Tabs() {
  return (
    <Tab.Navigator
      screenOptions={{
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
      }}
    >
      <Tab.Screen
        name="Scan"
        component={CameraScreen}
        options={{
          tabBarIcon: ({ focused }) => <TabIcon glyph="📸" focused={focused} />,
        }}
      />
      <Tab.Screen
        name="Collection"
        component={CollectionScreen}
        options={{
          tabBarIcon: ({ focused }) => <TabIcon glyph="📚" focused={focused} />,
        }}
      />
      <Tab.Screen
        name="Dashboard"
        component={DashboardScreen}
        options={{
          tabBarIcon: ({ focused }) => <TabIcon glyph="📈" focused={focused} />,
        }}
      />
    </Tab.Navigator>
  );
}

export default function App() {
  return (
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
      <StatusBar style="light" />
      <Stack.Navigator screenOptions={{ headerStyle: { backgroundColor: '#0a0a12' }, headerTintColor: '#ffd21f' }}>
        <Stack.Screen
          name="Tabs"
          component={Tabs}
          options={{ headerShown: false, title: 'ComicGrade AI' }}
        />
        <Stack.Screen name="ComicDetail" component={ComicDetailScreen} />
      </Stack.Navigator>
    </NavigationContainer>
  );
}