/// <reference types="jquery" />

// jQuery (CDN global)
declare const $: JQueryStatic;
declare const jQuery: JQueryStatic;

// GSAP 1.x / TweenMax (CDN global: cdnjs.cloudflare.com/ajax/libs/gsap/1.19.1/TweenMax.min.js)
interface TweenVars {
  [key: string]: unknown;
  ease?: EaseLookup;
  delay?: number;
  force3D?: boolean;
  onComplete?: () => void;
}
interface EaseLookup {
  easeIn: EaseLookup;
  easeOut: EaseLookup;
  easeInOut: EaseLookup;
}
declare const Power1: EaseLookup;
declare const Power2: EaseLookup;
declare const Power3: EaseLookup;
declare const TweenMax: {
  set(target: object | object[], vars: TweenVars): void;
  to(target: object | object[], duration: number, vars: TweenVars): void;
  staggerFromTo(
    targets: object | object[],
    duration: number,
    fromVars: TweenVars,
    toVars: TweenVars,
    stagger?: number,
    onCompleteAll?: () => void
  ): void;
  killTweensOf(target: object | object[]): void;
};

// QRCode (CDN global: qrcodejs)
interface QRCodeOptions {
  text: string;
  width?: number;
  height?: number;
  colorDark?: string;
  colorLight?: string;
  correctLevel?: number;
}
declare const QRCode: {
  new(element: HTMLElement, options: QRCodeOptions): void;
  CorrectLevel: { L: number; M: number; Q: number; H: number };
};

// Hls.js (CDN global: cdn.jsdelivr.net/npm/hls.js@latest)
declare const Hls: typeof import('hls.js').default;

// Three.js (CDN global: dynamically loaded in particleEffect.ts)
declare const THREE: typeof import('three');

// カスタム DOM プロパティ
interface HTMLVideoElement {
  _bgReady?: boolean;
}

// グローバル window 拡張
interface Window {
  API_BASE: string;
}
