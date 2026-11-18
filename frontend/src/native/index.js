// Native (Capacitor) integration. Everything here is a no-op in a normal browser.
import { Capacitor } from '@capacitor/core';
import { App } from '@capacitor/app';
import { StatusBar, Style } from '@capacitor/status-bar';
import { SplashScreen } from '@capacitor/splash-screen';

export const isNative = Capacitor.isNativePlatform();

export function initNative() {
  if (!isNative) return;

  document.documentElement.classList.add('native-app');

  StatusBar.setStyle({ style: Style.Light }).catch(() => {});
  StatusBar.setBackgroundColor({ color: '#FBF9F5' }).catch(() => {});

  // Android hardware back button: go back in app history, or exit at the root.
  App.addListener('backButton', ({ canGoBack }) => {
    const atRoot = ['/', '/auth'].includes(window.location.pathname);
    if (canGoBack && !atRoot) {
      window.history.back();
    } else {
      App.exitApp();
    }
  });

  SplashScreen.hide().catch(() => {});
}
