import 'dart:ui';
import 'package:flutter/material.dart';

class XlDuration {
  static const instant = Duration(milliseconds: 80);
  static const micro = Duration(milliseconds: 120);
  static const fast = Duration(milliseconds: 180);
  static const normal = Duration(milliseconds: 260);
  static const medium = Duration(milliseconds: 320);
  static const slow = Duration(milliseconds: 380);
  static const slower = Duration(milliseconds: 460);
  static const slowest = Duration(milliseconds: 560);
  static const crawl = Duration(milliseconds: 720);
  static const creep = Duration(milliseconds: 900);
}

class XlCurve {
  static const standard = Cubic(0.22, 0.61, 0.36, 1.0);
  static const spring = Cubic(0.34, 1.20, 0.64, 1.0);
  static const springSoft = Cubic(0.34, 1.08, 0.64, 1.0);
  static const sharp = Cubic(0.4, 0, 0.2, 1);
  static const bounce = Cubic(0.68, -0.55, 0.265, 1.55);
  static const easeOut = Cubic(0.16, 1, 0.3, 1);
  static const easeInOut = Cubic(0.65, 0, 0.35, 1);
  static const overshoot = Cubic(0.34, 1.56, 0.64, 1);
}

class XlRadius {
  static const micro = 6.0;
  static const xs = 8.0;
  static const sm = 10.0;
  static const md = 12.0;
  static const ml = 14.0;
  static const lg = 16.0;
  static const xl = 20.0;
  static const xxl = 22.0;
  static const xxxl = 26.0;
  static const huge = 32.0;
  static const giant = 40.0;
  static const pill = 999.0;
}

class XlSpace {
  static const zero = 0.0;
  static const hair = 2.0;
  static const tiny = 4.0;
  static const xxs = 6.0;
  static const xs = 8.0;
  static const sm = 10.0;
  static const md = 12.0;
  static const ml = 14.0;
  static const lg = 16.0;
  static const xl = 18.0;
  static const xxl = 22.0;
  static const xxxl = 26.0;
  static const huge = 32.0;
  static const giant = 40.0;
  static const mega = 48.0;
  static const giga = 64.0;
}

class XlFont {
  static const h1 = 34.0;
  static const h2 = 28.0;
  static const h3 = 24.0;
  static const h4 = 20.0;
  static const h5 = 18.0;
  static const h6 = 16.0;
  static const body = 15.0;
  static const bodySm = 14.0;
  static const caption = 13.0;
  static const captionSm = 12.0;
  static const label = 11.0;
  static const labelSm = 10.0;
  static const micro = 9.0;
}

class XlIconSize {
  static const micro = 12.0;
  static const xs = 14.0;
  static const sm = 16.0;
  static const md = 18.0;
  static const lg = 20.0;
  static const xl = 22.0;
  static const xxl = 26.0;
  static const huge = 32.0;
  static const giant = 40.0;
}

class XlElevation {
  static const flat = 0.0;
  static const low = 1.0;
  static const medium = 2.0;
  static const high = 3.0;
  static const highest = 4.0;
}

class XlOpacity {
  static const transparent = 0.0;
  static const ghost = 0.04;
  static const faint = 0.08;
  static const whisper = 0.12;
  static const soft = 0.18;
  static const light = 0.28;
  static const medium = 0.42;
  static const strong = 0.56;
  static const vivid = 0.72;
  static const bold = 0.85;
  static const solid = 1.0;
}

class XlBreakpoint {
  static const mobileSm = 380.0;
  static const mobile = 600.0;
  static const tabletSm = 760.0;
  static const tablet = 860.0;
  static const desktopSm = 1024.0;
  static const desktop = 1280.0;
  static const desktopLg = 1600.0;
}

class XlLetterSpacing {
  static const tighter = -1.2;
  static const tight = -0.8;
  static const normal = -0.3;
  static const relaxed = 0.0;
  static const wide = 0.3;
  static const wider = 0.6;
  static const widest = 1.2;
  static const mega = 2.0;
  static const ultra = 3.0;
}

class XlLineHeight {
  static const dense = 1.2;
  static const snug = 1.35;
  static const normal = 1.5;
  static const relaxed = 1.6;
  static const loose = 1.75;
}

@immutable
class XlPalette extends ThemeExtension<XlPalette> {
  final bool dark;
  final Color bg;
  final Color bgSoft;
  final Color bgDeep;
  final Color surface;
  final Color surfaceHi;
  final Color surfaceLo;
  final Color surfaceAlt;
  final Color screen;
  final Color screenSoft;
  final Color edge;
  final Color edgeStrong;
  final Color edgeSoft;
  final Color text1;
  final Color text2;
  final Color text3;
  final Color text4;
  final Color decor;
  final Color decorSoft;
  final Color pink;
  final Color pink2;
  final Color pink3;
  final Color pinkSoft;
  final Color gold;
  final Color gold2;
  final Color gold3;
  final Color goldSoft;
  final Color violet;
  final Color violet2;
  final Color violet3;
  final Color green;
  final Color green2;
  final Color green3;
  final Color red;
  final Color red2;
  final Color blue;
  final Color blue2;
  final Color orange;
  final Color orange2;
  final Color cyan;
  final Color cyan2;
  final Color shDark;
  final Color shDarker;
  final Color shDarkest;
  final Color shLight;
  final Color shLighter;
  final Color shLighter2;
  final Color shDeep;
  final Color shDeep2;
  final Color btnInk;
  final Color btnInk2;
  final Color btnHi;
  final Color btnHi2;
  final Color ripple;
  final Color rippleSoft;
  final Color divider;
  final Color dividerStrong;
  final Color dividerSoft;
  final Color scrim;
  final Color scrimSoft;
  final LinearGradient face;
  final LinearGradient faceHi;
  final LinearGradient faceLo;
  final LinearGradient faceV;
  final LinearGradient faceH;
  final LinearGradient faceAngled;
  final LinearGradient gradBrand;
  final LinearGradient gradBrandH;
  final LinearGradient gradBrandV;
  final LinearGradient gradText;
  final LinearGradient gradTextH;
  final LinearGradient gradGold;
  final LinearGradient gradGoldSoft;
  final LinearGradient gradGreen;
  final LinearGradient gradViolet;
  final LinearGradient gradRed;
  final LinearGradient gradBlue;
  final LinearGradient gradCyan;
  final LinearGradient gradSunset;
  final LinearGradient gradOcean;
  final LinearGradient btnFace;
  final LinearGradient btnFaceV;
  final LinearGradient btnFacePressed;
  final LinearGradient btnFaceGhost;
  final LinearGradient screenGlow;
  final LinearGradient screenGlowPink;
  final LinearGradient screenGlowGold;
  final LinearGradient navFace;
  final LinearGradient navFaceDeep;
  final LinearGradient sidebarFace;
  final LinearGradient sidebarTop;
  final LinearGradient sidebarBottom;
  final LinearGradient cardAccent;
  final LinearGradient cardGold;
  final LinearGradient cardGreen;
  final LinearGradient cardViolet;
  final LinearGradient dividerGrad;
  final LinearGradient shimmer;
  final Color glow1;
  final Color glow2;
  final Color glow3;
  final Color glow4;
  final Color glow5;
  final double noiseOpacity;

  const XlPalette({
    required this.dark,
    required this.bg,
    required this.bgSoft,
    required this.bgDeep,
    required this.surface,
    required this.surfaceHi,
    required this.surfaceLo,
    required this.surfaceAlt,
    required this.screen,
    required this.screenSoft,
    required this.edge,
    required this.edgeStrong,
    required this.edgeSoft,
    required this.text1,
    required this.text2,
    required this.text3,
    required this.text4,
    required this.decor,
    required this.decorSoft,
    required this.pink,
    required this.pink2,
    required this.pink3,
    required this.pinkSoft,
    required this.gold,
    required this.gold2,
    required this.gold3,
    required this.goldSoft,
    required this.violet,
    required this.violet2,
    required this.violet3,
    required this.green,
    required this.green2,
    required this.green3,
    required this.red,
    required this.red2,
    required this.blue,
    required this.blue2,
    required this.orange,
    required this.orange2,
    required this.cyan,
    required this.cyan2,
    required this.shDark,
    required this.shDarker,
    required this.shDarkest,
    required this.shLight,
    required this.shLighter,
    required this.shLighter2,
    required this.shDeep,
    required this.shDeep2,
    required this.btnInk,
    required this.btnInk2,
    required this.btnHi,
    required this.btnHi2,
    required this.ripple,
    required this.rippleSoft,
    required this.divider,
    required this.dividerStrong,
    required this.dividerSoft,
    required this.scrim,
    required this.scrimSoft,
    required this.face,
    required this.faceHi,
    required this.faceLo,
    required this.faceV,
    required this.faceH,
    required this.faceAngled,
    required this.gradBrand,
    required this.gradBrandH,
    required this.gradBrandV,
    required this.gradText,
    required this.gradTextH,
    required this.gradGold,
    required this.gradGoldSoft,
    required this.gradGreen,
    required this.gradViolet,
    required this.gradRed,
    required this.gradBlue,
    required this.gradCyan,
    required this.gradSunset,
    required this.gradOcean,
    required this.btnFace,
    required this.btnFaceV,
    required this.btnFacePressed,
    required this.btnFaceGhost,
    required this.screenGlow,
    required this.screenGlowPink,
    required this.screenGlowGold,
    required this.navFace,
    required this.navFaceDeep,
    required this.sidebarFace,
    required this.sidebarTop,
    required this.sidebarBottom,
    required this.cardAccent,
    required this.cardGold,
    required this.cardGreen,
    required this.cardViolet,
    required this.dividerGrad,
    required this.shimmer,
    required this.glow1,
    required this.glow2,
    required this.glow3,
    required this.glow4,
    required this.glow5,
    required this.noiseOpacity,
  });

  static const dark = XlPalette(
    dark: true,
    bg: Color(0xFF17131D),
    bgSoft: Color(0xFF1A1520),
    bgDeep: Color(0xFF0F0B14),
    surface: Color(0xFF1C1724),
    surfaceHi: Color(0xFF241C2E),
    surfaceLo: Color(0xFF161119),
    surfaceAlt: Color(0xFF201926),
    screen: Color(0xFF120E18),
    screenSoft: Color(0xFF16111C),
    edge: Color(0x0EFFFFFF),
    edgeStrong: Color(0x1AFFFFFF),
    edgeSoft: Color(0x08FFFFFF),
    text1: Color(0xFFF2E9EF),
    text2: Color(0xFFBFB0C2),
    text3: Color(0xFFA294A6),
    text4: Color(0xFF857788),
    decor: Color(0xFF8E7E92),
    decorSoft: Color(0xFF6A5E6E),
    pink: Color(0xFFFF6FA5),
    pink2: Color(0xFFFFA8C8),
    pink3: Color(0xFFFFD9E8),
    pinkSoft: Color(0x33FF6FA5),
    gold: Color(0xFFE8C46A),
    gold2: Color(0xFFF7E3A8),
    gold3: Color(0xFFFFF6DC),
    goldSoft: Color(0x33E8C46A),
    violet: Color(0xFFA874F0),
    violet2: Color(0xFFC9A6FF),
    violet3: Color(0xFFE5D4FF),
    green: Color(0xFF5FD9A8),
    green2: Color(0xFF9BEDCB),
    green3: Color(0xFFD5F7E7),
    red: Color(0xFFFF6B6B),
    red2: Color(0xFFFFA8A8),
    blue: Color(0xFF6BA8FF),
    blue2: Color(0xFFA8C9FF),
    orange: Color(0xFFFF9F5A),
    orange2: Color(0xFFFFC499),
    cyan: Color(0xFF5AD9E8),
    cyan2: Color(0xFFA5EDF5),
    shDark: Color(0x8C000000),
    shDarker: Color(0xA6000000),
    shDarkest: Color(0xC4000000),
    shLight: Color(0x0BFFFFFF),
    shLighter: Color(0x14FFFFFF),
    shLighter2: Color(0x1FFFFFFF),
    shDeep: Color(0xB3000000),
    shDeep2: Color(0xD9000000),
    btnInk: Color(0xFF3A1226),
    btnInk2: Color(0xFF4D1A34),
    btnHi: Color(0x59FFFFFF),
    btnHi2: Color(0x80FFFFFF),
    ripple: Color(0x40FF6FA5),
    rippleSoft: Color(0x26FF6FA5),
    divider: Color(0x14FFFFFF),
    dividerStrong: Color(0x26FFFFFF),
    dividerSoft: Color(0x0AFFFFFF),
    scrim: Color(0xCC0A060F),
    scrimSoft: Color(0x800A060F),
    face: LinearGradient(
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
      colors: [Color(0xFF241C2E), Color(0xFF1C1724), Color(0xFF161119)],
      stops: [0.0, 0.55, 1.0],
    ),
    faceHi: LinearGradient(
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
      colors: [Color(0xFF2C2238), Color(0xFF241C2E), Color(0xFF1E1726)],
      stops: [0.0, 0.5, 1.0],
    ),
    faceLo: LinearGradient(
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
      colors: [Color(0xFF15101B), Color(0xFF100B15), Color(0xFF0B0710)],
      stops: [0.0, 0.5, 1.0],
    ),
    faceV: LinearGradient(
      begin: Alignment.topCenter,
      end: Alignment.bottomCenter,
      colors: [Color(0xFF241C2E), Color(0xFF161119)],
    ),
    faceH: LinearGradient(
      begin: Alignment.centerLeft,
      end: Alignment.centerRight,
      colors: [Color(0xFF241C2E), Color(0xFF161119)],
    ),
    faceAngled: LinearGradient(
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
      colors: [Color(0xFF241C2E), Color(0xFF1A1520), Color(0xFF161119)],
    ),
    gradBrand: LinearGradient(
      colors: [Color(0xFFFF6FA5), Color(0xFFFF9FBE), Color(0xFFE8C46A)],
      stops: [0.0, 0.45, 1.0],
    ),
    gradBrandH: LinearGradient(
      begin: Alignment.centerLeft,
      end: Alignment.centerRight,
      colors: [Color(0xFFFF6FA5), Color(0xFFFF9FBE), Color(0xFFE8C46A)],
      stops: [0.0, 0.5, 1.0],
    ),
    gradBrandV: LinearGradient(
      begin: Alignment.topCenter,
      end: Alignment.bottomCenter,
      colors: [Color(0xFFFF9FBE), Color(0xFFFF6FA5), Color(0xFFE8C46A)],
      stops: [0.0, 0.55, 1.0],
    ),
    gradText: LinearGradient(
      colors: [Color(0xFFFFD9E8), Color(0xFFFF8FB8), Color(0xFFF7E3A8), Color(0xFFFFB9D2)],
      stops: [0.0, 0.35, 0.7, 1.0],
    ),
    gradTextH: LinearGradient(
      begin: Alignment.centerLeft,
      end: Alignment.centerRight,
      colors: [Color(0xFFFFD9E8), Color(0xFFFF8FB8), Color(0xFFF7E3A8)],
      stops: [0.0, 0.5, 1.0],
    ),
    gradGold: LinearGradient(
      colors: [Color(0xFFE8C46A), Color(0xFFF7E3A8), Color(0xFFE8C46A)],
      stops: [0.0, 0.5, 1.0],
    ),
    gradGoldSoft: LinearGradient(
      colors: [Color(0x59E8C46A), Color(0x33E8C46A)],
    ),
    gradGreen: LinearGradient(
      colors: [Color(0xFF5FD9A8), Color(0xFF9BEDCB)],
    ),
    gradViolet: LinearGradient(
      colors: [Color(0xFFA874F0), Color(0xFFC9A6FF)],
    ),
    gradRed: LinearGradient(
      colors: [Color(0xFFFF6B6B), Color(0xFFFFA8A8)],
    ),
    gradBlue: LinearGradient(
      colors: [Color(0xFF6BA8FF), Color(0xFFA8C9FF)],
    ),
    gradCyan: LinearGradient(
      colors: [Color(0xFF5AD9E8), Color(0xFFA5EDF5)],
    ),
    gradSunset: LinearGradient(
      colors: [Color(0xFFFF9F5A), Color(0xFFFF6FA5), Color(0xFFA874F0)],
      stops: [0.0, 0.5, 1.0],
    ),
    gradOcean: LinearGradient(
      colors: [Color(0xFF5AD9E8), Color(0xFF6BA8FF), Color(0xFFA874F0)],
      stops: [0.0, 0.5, 1.0],
    ),
    btnFace: LinearGradient(
      colors: [Color(0xFFFF6FA5), Color(0xFFFF9FBE), Color(0xFFE8C46A)],
      stops: [0.0, 0.45, 1.0],
    ),
    btnFaceV: LinearGradient(
      begin: Alignment.topCenter,
      end: Alignment.bottomCenter,
      colors: [Color(0xFFFF9FBE), Color(0xFFFF6FA5), Color(0xFFE8C46A)],
      stops: [0.0, 0.55, 1.0],
    ),
    btnFacePressed: LinearGradient(
      colors: [Color(0xFFE85A8A), Color(0xFFE88FAA), Color(0xFFD4B05A)],
      stops: [0.0, 0.45, 1.0],
    ),
    btnFaceGhost: LinearGradient(
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
      colors: [Color(0x14FFFFFF), Color(0x08FFFFFF)],
    ),
    screenGlow: RadialGradient(
      colors: [Color(0x1AFF6FA5), Color(0x00000000)],
    ),
    screenGlowPink: RadialGradient(
      colors: [Color(0x40FF6FA5), Color(0x00000000)],
    ),
    screenGlowGold: RadialGradient(
      colors: [Color(0x33E8C46A), Color(0x00000000)],
    ),
    navFace: LinearGradient(
      begin: Alignment.topCenter,
      end: Alignment.bottomCenter,
      colors: [Color(0xFF241C2E), Color(0xFF17131D)],
    ),
    navFaceDeep: LinearGradient(
      begin: Alignment.topCenter,
      end: Alignment.bottomCenter,
      colors: [Color(0xFF2A2134), Color(0xFF1C1724)],
    ),
    sidebarFace: LinearGradient(
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
      colors: [Color(0xFF241C2E), Color(0xFF1C1724), Color(0xFF15101B)],
      stops: [0.0, 0.55, 1.0],
    ),
    sidebarTop: LinearGradient(
      begin: Alignment.topCenter,
      end: Alignment.bottomCenter,
      colors: [Color(0xFF2A2134), Color(0xFF1C1724)],
    ),
    sidebarBottom: LinearGradient(
      begin: Alignment.topCenter,
      end: Alignment.bottomCenter,
      colors: [Color(0xFF1C1724), Color(0xFF100B15)],
    ),
    cardAccent: LinearGradient(
      colors: [Color(0x1AFF6FA5), Color(0x0DE8C46A)],
    ),
    cardGold: LinearGradient(
      colors: [Color(0x1AE8C46A), Color(0x0DE8C46A)],
    ),
    cardGreen: LinearGradient(
      colors: [Color(0x1A5FD9A8), Color(0x0D5FD9A8)],
    ),
    cardViolet: LinearGradient(
      colors: [Color(0x1AA874F0), Color(0x0DA874F0)],
    ),
    dividerGrad: LinearGradient(
      colors: [Color(0x00FFFFFF), Color(0x14FFFFFF), Color(0x00FFFFFF)],
      stops: [0.0, 0.5, 1.0],
    ),
    shimmer: LinearGradient(
      colors: [Color(0x00FFFFFF), Color(0x26FFFFFF), Color(0x00FFFFFF)],
      stops: [0.0, 0.5, 1.0],
    ),
    glow1: Color(0x14FF6FA5),
    glow2: Color(0x0DE8C46A),
    glow3: Color(0x0DA874F0),
    glow4: Color(0x0A5FD9A8),
    glow5: Color(0x086BA8FF),
    noiseOpacity: 0.03,
  );

  static const light = XlPalette(
    dark: false,
    bg: Color(0xFFE9E4EE),
    bgSoft: Color(0xFFEDE8F2),
    bgDeep: Color(0xFFDFD8E7),
    surface: Color(0xFFECE7F1),
    surfaceHi: Color(0xFFF6F2F9),
    surfaceLo: Color(0xFFDFD8E7),
    surfaceAlt: Color(0xFFE4DEEC),
    screen: Color(0xFFE0D9E7),
    screenSoft: Color(0xFFE5DFEB),
    edge: Color(0xD9FFFFFF),
    edgeStrong: Color(0xF2FFFFFF),
    edgeSoft: Color(0x99FFFFFF),
    text1: Color(0xFF2B2032),
    text2: Color(0xFF5F5268),
    text3: Color(0xFF7B6E85),
    text4: Color(0xFF93859E),
    decor: Color(0xFF8A7C93),
    decorSoft: Color(0xFFA89BB0),
    pink: Color(0xFFD94C7C),
    pink2: Color(0xFFC2416F),
    pink3: Color(0xFFA83158),
    pinkSoft: Color(0x33D94C7C),
    gold: Color(0xFFA67C1E),
    gold2: Color(0xFF8A6A16),
    gold3: Color(0xFF6F5511),
    goldSoft: Color(0x33A67C1E),
    violet: Color(0xFF8A5CC0),
    violet2: Color(0xFFA67CD9),
    violet3: Color(0xFF6E459E),
    green: Color(0xFF2A9A6E),
    green2: Color(0xFF1F7B58),
    green3: Color(0xFF145A40),
    red: Color(0xFFD94C4C),
    red2: Color(0xFFB83A3A),
    blue: Color(0xFF3A7BD9),
    blue2: Color(0xFF2A5FA8),
    orange: Color(0xFFD9803A),
    orange2: Color(0xFFB86628),
    cyan: Color(0xFF2A9AA8),
    cyan2: Color(0xFF1F7B85),
    shDark: Color(0x4D5D4A72),
    shDarker: Color(0x665D4A72),
    shDarkest: Color(0x805D4A72),
    shLight: Color(0xF2FFFFFF),
    shLighter: Color(0xFFFFFFFF),
    shLighter2: Color(0xFFFFFFFF),
    shDeep: Color(0x805D4A72),
    shDeep2: Color(0x995D4A72),
    btnInk: Color(0xFFFFA8C8),
    btnInk2: Color(0xFFFFD9E8),
    btnHi: Color(0x33FFFFFF),
    btnHi2: Color(0x59FFFFFF),
    ripple: Color(0x30D94C7C),
    rippleSoft: Color(0x1FD94C7C),
    divider: Color(0x1A5D4A72),
    dividerStrong: Color(0x335D4A72),
    dividerSoft: Color(0x0D5D4A72),
    scrim: Color(0x99E9E4EE),
    scrimSoft: Color(0x66E9E4EE),
    face: LinearGradient(
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
      colors: [Color(0xFFF6F2F9), Color(0xFFECE7F1), Color(0xFFDFD8E7)],
      stops: [0.0, 0.55, 1.0],
    ),
    faceHi: LinearGradient(
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
      colors: [Color(0xFFFAF6FC), Color(0xFFF2EDF6), Color(0xFFECE7F1)],
      stops: [0.0, 0.5, 1.0],
    ),
    faceLo: LinearGradient(
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
      colors: [Color(0xFFD8D0E2), Color(0xFFCDC4D8), Color(0xFFC2B8CE)],
      stops: [0.0, 0.5, 1.0],
    ),
    faceV: LinearGradient(
      begin: Alignment.topCenter,
      end: Alignment.bottomCenter,
      colors: [Color(0xFFF6F2F9), Color(0xFFDFD8E7)],
    ),
    faceH: LinearGradient(
      begin: Alignment.centerLeft,
      end: Alignment.centerRight,
      colors: [Color(0xFFF6F2F9), Color(0xFFDFD8E7)],
    ),
    faceAngled: LinearGradient(
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
      colors: [Color(0xFFF6F2F9), Color(0xFFEDE8F2), Color(0xFFDFD8E7)],
    ),
    gradBrand: LinearGradient(
      colors: [Color(0xFFE75C90), Color(0xFFF0A8C6), Color(0xFFE8C46A)],
      stops: [0.0, 0.45, 1.0],
    ),
    gradBrandH: LinearGradient(
      begin: Alignment.centerLeft,
      end: Alignment.centerRight,
      colors: [Color(0xFFE75C90), Color(0xFFF0A8C6), Color(0xFFE8C46A)],
      stops: [0.0, 0.5, 1.0],
    ),
    gradBrandV: LinearGradient(
      begin: Alignment.topCenter,
      end: Alignment.bottomCenter,
      colors: [Color(0xFFF0A8C6), Color(0xFFE75C90), Color(0xFFE8C46A)],
      stops: [0.0, 0.55, 1.0],
    ),
    gradText: LinearGradient(
      colors: [Color(0xFFC2416F), Color(0xFFD94C7C), Color(0xFFA67C1E)],
      stops: [0.0, 0.4, 1.0],
    ),
    gradTextH: LinearGradient(
      begin: Alignment.centerLeft,
      end: Alignment.centerRight,
      colors: [Color(0xFFC2416F), Color(0xFFD94C7C), Color(0xFFA67C1E)],
      stops: [0.0, 0.5, 1.0],
    ),
    gradGold: LinearGradient(
      colors: [Color(0xFFA67C1E), Color(0xFFC9A13A), Color(0xFFA67C1E)],
      stops: [0.0, 0.5, 1.0],
    ),
    gradGoldSoft: LinearGradient(
      colors: [Color(0x40A67C1E), Color(0x26A67C1E)],
    ),
    gradGreen: LinearGradient(
      colors: [Color(0xFF2A9A6E), Color(0xFF5FD9A8)],
    ),
    gradViolet: LinearGradient(
      colors: [Color(0xFF8A5CC0), Color(0xFFA67CD9)],
    ),
    gradRed: LinearGradient(
      colors: [Color(0xFFD94C4C), Color(0xFFE88A8A)],
    ),
    gradBlue: LinearGradient(
      colors: [Color(0xFF3A7BD9), Color(0xFF7BA8E8)],
    ),
    gradCyan: LinearGradient(
      colors: [Color(0xFF2A9AA8), Color(0xFF7BC8D4)],
    ),
    gradSunset: LinearGradient(
      colors: [Color(0xFFD9803A), Color(0xFFD94C7C), Color(0xFF8A5CC0)],
      stops: [0.0, 0.5, 1.0],
    ),
    gradOcean: LinearGradient(
      colors: [Color(0xFF2A9AA8), Color(0xFF3A7BD9), Color(0xFF8A5CC0)],
      stops: [0.0, 0.5, 1.0],
    ),
    btnFace: LinearGradient(
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
      colors: [Color(0xFF352A42), Color(0xFF251D2F)],
    ),
    btnFaceV: LinearGradient(
      begin: Alignment.topCenter,
      end: Alignment.bottomCenter,
      colors: [Color(0xFF3D3048), Color(0xFF251D2F)],
    ),
    btnFacePressed: LinearGradient(
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
      colors: [Color(0xFF2A2134), Color(0xFF1C1724)],
    ),
    btnFaceGhost: LinearGradient(
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
      colors: [Color(0x0D5D4A72), Color(0x055D4A72)],
    ),
    screenGlow: RadialGradient(
      colors: [Color(0x1AD94C7C), Color(0x00000000)],
    ),
    screenGlowPink: RadialGradient(
      colors: [Color(0x33D94C7C), Color(0x00000000)],
    ),
    screenGlowGold: RadialGradient(
      colors: [Color(0x33A67C1E), Color(0x00000000)],
    ),
    navFace: LinearGradient(
      begin: Alignment.topCenter,
      end: Alignment.bottomCenter,
      colors: [Color(0xFFF6F2F9), Color(0xFFECE7F1)],
    ),
    navFaceDeep: LinearGradient(
      begin: Alignment.topCenter,
      end: Alignment.bottomCenter,
      colors: [Color(0xFFFAF6FC), Color(0xFFECE7F1)],
    ),
    sidebarFace: LinearGradient(
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
      colors: [Color(0xFFF6F2F9), Color(0xFFECE7F1), Color(0xFFDFD8E7)],
      stops: [0.0, 0.55, 1.0],
    ),
    sidebarTop: LinearGradient(
      begin: Alignment.topCenter,
      end: Alignment.bottomCenter,
      colors: [Color(0xFFFAF6FC), Color(0xFFECE7F1)],
    ),
    sidebarBottom: LinearGradient(
      begin: Alignment.topCenter,
      end: Alignment.bottomCenter,
      colors: [Color(0xFFECE7F1), Color(0xFFCDC4D8)],
    ),
    cardAccent: LinearGradient(
      colors: [Color(0x1AD94C7C), Color(0x0DA67C1E)],
    ),
    cardGold: LinearGradient(
      colors: [Color(0x1AA67C1E), Color(0x0DA67C1E)],
    ),
    cardGreen: LinearGradient(
      colors: [Color(0x1A2A9A6E), Color(0x0D2A9A6E)],
    ),
    cardViolet: LinearGradient(
      colors: [Color(0x1A8A5CC0), Color(0x0D8A5CC0)],
    ),
    dividerGrad: LinearGradient(
      colors: [Color(0x005D4A72), Color(0x1A5D4A72), Color(0x005D4A72)],
      stops: [0.0, 0.5, 1.0],
    ),
    shimmer: LinearGradient(
      colors: [Color(0x00FFFFFF), Color(0x80FFFFFF), Color(0x00FFFFFF)],
      stops: [0.0, 0.5, 1.0],
    ),
    glow1: Color(0x1AD94C7C),
    glow2: Color(0x1FA67C1E),
    glow3: Color(0x148A5CC0),
    glow4: Color(0x142A9A6E),
    glow5: Color(0x143A7BD9),
    noiseOpacity: 0.025,
  );

  static XlPalette of(BuildContext c) =>
      Theme.of(c).extension<XlPalette>() ?? dark;

  List<BoxShadow> get raisedUltra => [
    BoxShadow(color: shDark, offset: const Offset(18, 18), blurRadius: 36, spreadRadius: -4),
    BoxShadow(color: shLight, offset: const Offset(-18, -18), blurRadius: 36, spreadRadius: -4),
  ];
  List<BoxShadow> get raisedXxxl => [
    BoxShadow(color: shDark, offset: const Offset(16, 16), blurRadius: 32, spreadRadius: -3),
    BoxShadow(color: shLight, offset: const Offset(-16, -16), blurRadius: 32, spreadRadius: -3),
  ];
  List<BoxShadow> get raisedXxl => [
    BoxShadow(color: shDark, offset: const Offset(14, 14), blurRadius: 28, spreadRadius: -2),
    BoxShadow(color: shLight, offset: const Offset(-14, -14), blurRadius: 28, spreadRadius: -2),
  ];
  List<BoxShadow> get raisedXl => [
    BoxShadow(color: shDark, offset: const Offset(12, 12), blurRadius: 24),
    BoxShadow(color: shLight, offset: const Offset(-12, -12), blurRadius: 24),
  ];
  List<BoxShadow> get raised => [
    BoxShadow(color: shDark, offset: const Offset(9, 9), blurRadius: 20),
    BoxShadow(color: shLight, offset: const Offset(-9, -9), blurRadius: 20),
  ];
  List<BoxShadow> get raisedSm => [
    BoxShadow(color: shDark, offset: const Offset(5, 5), blurRadius: 11),
    BoxShadow(color: shLight, offset: const Offset(-5, -5), blurRadius: 11),
  ];
  List<BoxShadow> get raisedXs => [
    BoxShadow(color: shDark, offset: const Offset(3, 3), blurRadius: 7),
    BoxShadow(color: shLight, offset: const Offset(-3, -3), blurRadius: 7),
  ];
  List<BoxShadow> get raisedXxs => [
    BoxShadow(color: shDark, offset: const Offset(2, 2), blurRadius: 4),
    BoxShadow(color: shLight, offset: const Offset(-2, -2), blurRadius: 4),
  ];
  List<BoxShadow> get raisedHair => [
    BoxShadow(color: shDark, offset: const Offset(1, 1), blurRadius: 2),
    BoxShadow(color: shLight, offset: const Offset(-1, -1), blurRadius: 2),
  ];
  List<BoxShadow> get sunkenHair => [
    BoxShadow(color: shDark, offset: const Offset(1, 1), blurRadius: 2),
    BoxShadow(color: shLight, offset: const Offset(-1, -1), blurRadius: 2),
  ];
  List<BoxShadow> get sunkenXs => [
    BoxShadow(color: shDark, offset: const Offset(2, 2), blurRadius: 4),
    BoxShadow(color: shLight, offset: const Offset(-2, -2), blurRadius: 4),
  ];
  List<BoxShadow> get sunkenSm => [
    BoxShadow(color: shDark, offset: const Offset(3, 3), blurRadius: 7, spreadRadius: -1),
    BoxShadow(color: shLight, offset: const Offset(-3, -3), blurRadius: 7, spreadRadius: -1),
  ];
  List<BoxShadow> get sunken => [
    BoxShadow(color: shDark, offset: const Offset(6, 6), blurRadius: 12, spreadRadius: -2),
    BoxShadow(color: shLight, offset: const Offset(-6, -6), blurRadius: 12, spreadRadius: -2),
  ];
  List<BoxShadow> get sunkenLg => [
    BoxShadow(color: shDarker, offset: const Offset(8, 8), blurRadius: 15, spreadRadius: -2),
    BoxShadow(color: shLight, offset: const Offset(-8, -8), blurRadius: 15, spreadRadius: -2),
  ];
  List<BoxShadow> get sunkenDeep => [
    BoxShadow(color: shDeep, offset: const Offset(10, 10), blurRadius: 18, spreadRadius: -3),
    BoxShadow(color: shLight, offset: const Offset(-10, -10), blurRadius: 18, spreadRadius: -3),
  ];
  List<BoxShadow> get sunkenUltra => [
    BoxShadow(color: shDeep2, offset: const Offset(12, 12), blurRadius: 22, spreadRadius: -4),
    BoxShadow(color: shLight, offset: const Offset(-12, -12), blurRadius: 22, spreadRadius: -4),
  ];
  List<BoxShadow> glowPink({double intensity = 1.0}) => [
    BoxShadow(color: pink.withOpacity((dark ? 0.45 : 0.32) * intensity),
        blurRadius: 24, spreadRadius: -4),
  ];
  List<BoxShadow> glowGold({double intensity = 1.0}) => [
    BoxShadow(color: gold.withOpacity((dark ? 0.45 : 0.32) * intensity),
        blurRadius: 24, spreadRadius: -4),
  ];
  List<BoxShadow> glowGreen({double intensity = 1.0}) => [
    BoxShadow(color: green.withOpacity((dark ? 0.45 : 0.32) * intensity),
        blurRadius: 24, spreadRadius: -4),
  ];
  List<BoxShadow> glowViolet({double intensity = 1.0}) => [
    BoxShadow(color: violet.withOpacity((dark ? 0.45 : 0.32) * intensity),
        blurRadius: 24, spreadRadius: -4),
  ];
  List<BoxShadow> glowRed({double intensity = 1.0}) => [
    BoxShadow(color: red.withOpacity((dark ? 0.45 : 0.32) * intensity),
        blurRadius: 24, spreadRadius: -4),
  ];
  List<BoxShadow> glowBlue({double intensity = 1.0}) => [
    BoxShadow(color: blue.withOpacity((dark ? 0.45 : 0.32) * intensity),
        blurRadius: 24, spreadRadius: -4),
  ];
  List<BoxShadow> glowCyan({double intensity = 1.0}) => [
    BoxShadow(color: cyan.withOpacity((dark ? 0.45 : 0.32) * intensity),
        blurRadius: 24, spreadRadius: -4),
  ];
  List<BoxShadow> get innerTopHighlight => [
    BoxShadow(color: shLighter, offset: const Offset(0, 1), blurRadius: 0),
  ];
  List<BoxShadow> get innerBottomShade => [
    BoxShadow(color: shDark, offset: const Offset(0, -1), blurRadius: 0),
  ];
  List<BoxShadow> get borderRing => [
    BoxShadow(color: edge, spreadRadius: 0, blurRadius: 0),
  ];
  List<BoxShadow> get focusRing => [
    BoxShadow(color: pink.withOpacity(0.5), spreadRadius: 3, blurRadius: 0),
    BoxShadow(color: bg, spreadRadius: 1, blurRadius: 0),
  ];

  @override
  XlPalette copyWith({
    bool? dark, Color? bg, Color? bgSoft, Color? bgDeep,
    Color? surface, Color? surfaceHi, Color? surfaceLo, Color? surfaceAlt,
    Color? screen, Color? screenSoft,
    Color? edge, Color? edgeStrong, Color? edgeSoft,
    Color? text1, Color? text2, Color? text3, Color? text4,
    Color? decor, Color? decorSoft,
    Color? pink, Color? pink2, Color? pink3, Color? pinkSoft,
    Color? gold, Color? gold2, Color? gold3, Color? goldSoft,
    Color? violet, Color? violet2, Color? violet3,
    Color? green, Color? green2, Color? green3,
    Color? red, Color? red2, Color? blue, Color? blue2,
    Color? orange, Color? orange2, Color? cyan, Color? cyan2,
    Color? shDark, Color? shDarker, Color? shDarkest,
    Color? shLight, Color? shLighter, Color? shLighter2,
    Color? shDeep, Color? shDeep2,
    Color? btnInk, Color? btnInk2, Color? btnHi, Color? btnHi2,
    Color? ripple, Color? rippleSoft,
    Color? divider, Color? dividerStrong, Color? dividerSoft,
    Color? scrim, Color? scrimSoft,
    LinearGradient? face, LinearGradient? faceHi, LinearGradient? faceLo,
    LinearGradient? faceV, LinearGradient? faceH, LinearGradient? faceAngled,
    LinearGradient? gradBrand, LinearGradient? gradBrandH, LinearGradient? gradBrandV,
    LinearGradient? gradText, LinearGradient? gradTextH,
    LinearGradient? gradGold, LinearGradient? gradGoldSoft,
    LinearGradient? gradGreen, LinearGradient? gradViolet,
    LinearGradient? gradRed, LinearGradient? gradBlue,
    LinearGradient? gradCyan, LinearGradient? gradSunset, LinearGradient? gradOcean,
    LinearGradient? btnFace, LinearGradient? btnFaceV,
    LinearGradient? btnFacePressed, LinearGradient? btnFaceGhost,
    LinearGradient? screenGlow, LinearGradient? screenGlowPink, LinearGradient? screenGlowGold,
    LinearGradient? navFace, LinearGradient? navFaceDeep,
    LinearGradient? sidebarFace, LinearGradient? sidebarTop, LinearGradient? sidebarBottom,
    LinearGradient? cardAccent, LinearGradient? cardGold, LinearGradient? cardGreen,
    LinearGradient? cardViolet, LinearGradient? dividerGrad, LinearGradient? shimmer,
    Color? glow1, Color? glow2, Color? glow3, Color? glow4, Color? glow5,
    double? noiseOpacity,
  }) => this;

  @override
  XlPalette lerp(ThemeExtension<XlPalette>? other, double t) {
    if (other is! XlPalette) return this;
    return t < 0.5 ? this : other;
  }
}

class AppTheme {
  static ThemeData get darkTheme => _build(XlPalette.dark);
  static ThemeData get lightTheme => _build(XlPalette.light);

  static ThemeData _build(XlPalette p) {
    final brightness = p.dark ? Brightness.dark : Brightness.light;
    return ThemeData(
      useMaterial3: true, brightness: brightness,
      scaffoldBackgroundColor: p.bg, canvasColor: p.bg,
      dividerColor: p.divider, splashColor: Colors.transparent,
      highlightColor: Colors.transparent,
      hoverColor: p.pink.withOpacity(XlOpacity.ghost),
      focusColor: p.pink.withOpacity(XlOpacity.faint),
      disabledColor: p.decorSoft,
      colorScheme: ColorScheme.fromSeed(
        seedColor: p.pink, brightness: brightness,
        primary: p.pink, secondary: p.gold, surface: p.surface,
        error: p.red, onPrimary: p.btnInk,
      ),
      extensions: [p],
      textTheme: TextTheme(
        displayLarge: TextStyle(fontSize: 48, fontWeight: FontWeight.w800, color: p.text1, letterSpacing: XlLetterSpacing.tighter, height: XlLineHeight.dense),
        displayMedium: TextStyle(fontSize: 36, fontWeight: FontWeight.w800, color: p.text1, letterSpacing: XlLetterSpacing.tight, height: 1.1),
        displaySmall: TextStyle(fontSize: 32, fontWeight: FontWeight.w800, color: p.text1, letterSpacing: XlLetterSpacing.tight),
        headlineLarge: TextStyle(fontSize: XlFont.h1, fontWeight: FontWeight.w800, color: p.text1, letterSpacing: XlLetterSpacing.normal),
        headlineMedium: TextStyle(fontSize: XlFont.h2, fontWeight: FontWeight.w800, color: p.text1, letterSpacing: XlLetterSpacing.normal),
        headlineSmall: TextStyle(fontSize: XlFont.h3, fontWeight: FontWeight.w700, color: p.text1, letterSpacing: XlLetterSpacing.normal),
        titleLarge: TextStyle(fontSize: XlFont.h4, fontWeight: FontWeight.w700, color: p.text1),
        titleMedium: TextStyle(fontSize: XlFont.h5, fontWeight: FontWeight.w700, color: p.text1),
        titleSmall: TextStyle(fontSize: XlFont.h6, fontWeight: FontWeight.w600, color: p.text1),
        bodyLarge: TextStyle(fontSize: XlFont.body, color: p.text1, height: XlLineHeight.normal),
        bodyMedium: TextStyle(fontSize: XlFont.bodySm, color: p.text2, height: XlLineHeight.normal),
        bodySmall: TextStyle(fontSize: XlFont.caption, color: p.text3, height: XlLineHeight.normal),
        labelLarge: TextStyle(fontSize: XlFont.body, fontWeight: FontWeight.w700, color: p.text1),
        labelMedium: TextStyle(fontSize: XlFont.captionSm, fontWeight: FontWeight.w600, color: p.text2),
        labelSmall: TextStyle(fontSize: XlFont.label, fontWeight: FontWeight.w700, color: p.decor, letterSpacing: XlLetterSpacing.wide),
      ),
      scrollbarTheme: ScrollbarThemeData(
        thumbColor: WidgetStatePropertyAll(p.decor.withOpacity(XlOpacity.light)),
        trackColor: const WidgetStatePropertyAll(Colors.transparent),
        radius: const Radius.circular(XlRadius.pill),
        thickness: const WidgetStatePropertyAll(6),
      ),
    );
  }

  static BoxDecoration neuUltra(BuildContext c, {double r = XlRadius.xxxl}) {
    final p = XlPalette.of(c);
    return BoxDecoration(gradient: p.face, borderRadius: BorderRadius.circular(r),
        border: Border.all(color: p.edge, width: 1), boxShadow: p.raisedUltra);
  }
  static BoxDecoration neuXxxl(BuildContext c, {double r = XlRadius.xxxl}) {
    final p = XlPalette.of(c);
    return BoxDecoration(gradient: p.face, borderRadius: BorderRadius.circular(r),
        border: Border.all(color: p.edge, width: 1), boxShadow: p.raisedXxxl);
  }
  static BoxDecoration neuXxl(BuildContext c, {double r = XlRadius.xxl}) {
    final p = XlPalette.of(c);
    return BoxDecoration(gradient: p.face, borderRadius: BorderRadius.circular(r),
        border: Border.all(color: p.edge, width: 1), boxShadow: p.raisedXxl);
  }
  static BoxDecoration neuXl(BuildContext c, {double r = XlRadius.xl}) {
    final p = XlPalette.of(c);
    return BoxDecoration(gradient: p.face, borderRadius: BorderRadius.circular(r),
        border: Border.all(color: p.edge, width: 1), boxShadow: p.raisedXl);
  }
  static BoxDecoration neuLg(BuildContext c, {double r = XlRadius.xxl}) {
    final p = XlPalette.of(c);
    return BoxDecoration(gradient: p.face, borderRadius: BorderRadius.circular(r),
        border: Border.all(color: p.edge, width: 1), boxShadow: p.raised);
  }
  static BoxDecoration neu(BuildContext c, {double r = XlRadius.lg}) {
    final p = XlPalette.of(c);
    return BoxDecoration(gradient: p.face, borderRadius: BorderRadius.circular(r),
        border: Border.all(color: p.edge, width: 1), boxShadow: p.raisedSm);
  }
  static BoxDecoration neuSm(BuildContext c, {double r = XlRadius.md}) {
    final p = XlPalette.of(c);
    return BoxDecoration(gradient: p.face, borderRadius: BorderRadius.circular(r),
        border: Border.all(color: p.edge, width: 1), boxShadow: p.raisedXs);
  }
  static BoxDecoration neuXs(BuildContext c, {double r = XlRadius.sm}) {
    final p = XlPalette.of(c);
    return BoxDecoration(gradient: p.face, borderRadius: BorderRadius.circular(r),
        border: Border.all(color: p.edge, width: 1), boxShadow: p.raisedXs);
  }
  static BoxDecoration neuXxs(BuildContext c, {double r = XlRadius.xs}) {
    final p = XlPalette.of(c);
    return BoxDecoration(gradient: p.faceHi, borderRadius: BorderRadius.circular(r),
        border: Border.all(color: p.edge, width: 1), boxShadow: p.raisedXxs);
  }
  static BoxDecoration neuHair(BuildContext c, {double r = XlRadius.micro}) {
    final p = XlPalette.of(c);
    return BoxDecoration(gradient: p.faceHi, borderRadius: BorderRadius.circular(r),
        border: Border.all(color: p.edgeSoft, width: 1), boxShadow: p.raisedHair);
  }
  static BoxDecoration sunkenHair(BuildContext c, {double r = XlRadius.micro}) {
    final p = XlPalette.of(c);
    return BoxDecoration(color: p.surfaceHi, borderRadius: BorderRadius.circular(r),
        border: Border.all(color: p.shDark.withOpacity(p.dark ? 0.15 : 0.06), width: 1),
        boxShadow: p.sunkenHair);
  }
  static BoxDecoration sunkenXs(BuildContext c, {double r = XlRadius.sm}) {
    final p = XlPalette.of(c);
    return BoxDecoration(color: p.surface, borderRadius: BorderRadius.circular(r),
        border: Border.all(color: p.shDark.withOpacity(p.dark ? 0.22 : 0.10), width: 1),
        boxShadow: p.sunkenXs);
  }
  static BoxDecoration sunkenSm(BuildContext c, {double r = XlRadius.md}) {
    final p = XlPalette.of(c);
    return BoxDecoration(color: p.surface, borderRadius: BorderRadius.circular(r),
        border: Border.all(color: p.shDark.withOpacity(p.dark ? 0.26 : 0.11), width: 1),
        boxShadow: p.sunkenSm);
  }
  static BoxDecoration sunken(BuildContext c, {double r = XlRadius.md}) {
    final p = XlPalette.of(c);
    return BoxDecoration(color: p.surface, borderRadius: BorderRadius.circular(r),
        border: Border.all(color: p.shDark.withOpacity(p.dark ? 0.30 : 0.13), width: 1),
        boxShadow: p.sunken);
  }
  static BoxDecoration sunkenLg(BuildContext c, {double r = XlRadius.lg}) {
    final p = XlPalette.of(c);
    return BoxDecoration(color: p.surfaceLo, borderRadius: BorderRadius.circular(r),
        border: Border.all(color: p.shDark.withOpacity(p.dark ? 0.35 : 0.15), width: 1),
        boxShadow: p.sunkenLg);
  }
  static BoxDecoration sunkenDeep(BuildContext c, {double r = XlRadius.md}) {
    final p = XlPalette.of(c);
    return BoxDecoration(color: p.surfaceLo, borderRadius: BorderRadius.circular(r),
        border: Border.all(color: p.shDark.withOpacity(p.dark ? 0.38 : 0.17), width: 1),
        boxShadow: p.sunkenDeep);
  }
  static BoxDecoration sunkenUltra(BuildContext c, {double r = XlRadius.md}) {
    final p = XlPalette.of(c);
    return BoxDecoration(color: p.screen, borderRadius: BorderRadius.circular(r),
        border: Border.all(color: p.shDark.withOpacity(p.dark ? 0.45 : 0.20), width: 1),
        boxShadow: p.sunkenUltra);
  }
  static BoxDecoration screen(BuildContext c, {double r = XlRadius.md}) {
    final p = XlPalette.of(c);
    return BoxDecoration(color: p.screen, borderRadius: BorderRadius.circular(r),
        border: Border.all(color: p.shDark.withOpacity(p.dark ? 0.40 : 0.18), width: 1),
        boxShadow: p.sunkenDeep);
  }
  static BoxDecoration screenSoft(BuildContext c, {double r = XlRadius.md}) {
    final p = XlPalette.of(c);
    return BoxDecoration(color: p.screenSoft, borderRadius: BorderRadius.circular(r),
        border: Border.all(color: p.shDark.withOpacity(p.dark ? 0.35 : 0.15), width: 1),
        boxShadow: p.sunkenLg);
  }
  static BoxDecoration btn(BuildContext c, {double r = XlRadius.pill}) {
    final p = XlPalette.of(c);
    return BoxDecoration(gradient: p.btnFace, borderRadius: BorderRadius.circular(r),
        border: Border.all(color: Colors.white.withOpacity(p.dark ? 0.35 : 0.22), width: 1),
        boxShadow: p.raisedXs);
  }
  static BoxDecoration btnLg(BuildContext c, {double r = XlRadius.pill}) {
    final p = XlPalette.of(c);
    return BoxDecoration(gradient: p.btnFace, borderRadius: BorderRadius.circular(r),
        border: Border.all(color: Colors.white.withOpacity(p.dark ? 0.40 : 0.26), width: 1),
        boxShadow: p.raisedSm);
  }
  static BoxDecoration btnV(BuildContext c, {double r = XlRadius.pill}) {
    final p = XlPalette.of(c);
    return BoxDecoration(gradient: p.btnFaceV, borderRadius: BorderRadius.circular(r),
        border: Border.all(color: Colors.white.withOpacity(p.dark ? 0.35 : 0.22), width: 1),
        boxShadow: p.raisedXs);
  }
  static BoxDecoration btnPressed(BuildContext c, {double r = XlRadius.pill}) {
    final p = XlPalette.of(c);
    return BoxDecoration(gradient: p.btnFacePressed, borderRadius: BorderRadius.circular(r),
        border: Border.all(color: Colors.white.withOpacity(p.dark ? 0.18 : 0.10), width: 1),
        boxShadow: p.sunkenSm);
  }
  static BoxDecoration ghost(BuildContext c, {double r = XlRadius.pill}) {
    final p = XlPalette.of(c);
    return BoxDecoration(gradient: p.face, borderRadius: BorderRadius.circular(r),
        border: Border.all(color: p.edge, width: 1), boxShadow: p.raisedXs);
  }
  static BoxDecoration ghostPressed(BuildContext c, {double r = XlRadius.pill}) {
    final p = XlPalette.of(c);
    return BoxDecoration(color: p.surfaceLo, borderRadius: BorderRadius.circular(r),
        border: Border.all(color: p.shDark.withOpacity(p.dark ? 0.30 : 0.13), width: 1),
        boxShadow: p.sunkenSm);
  }
  static BoxDecoration glass(BuildContext c, {double r = XlRadius.lg}) {
    final p = XlPalette.of(c);
    return BoxDecoration(color: p.surface.withOpacity(p.dark ? 0.85 : 0.72),
        borderRadius: BorderRadius.circular(r),
        border: Border.all(color: p.edge, width: 1), boxShadow: p.raised);
  }
  static BoxDecoration glassDeep(BuildContext c, {double r = XlRadius.lg}) {
    final p = XlPalette.of(c);
    return BoxDecoration(color: p.surface.withOpacity(p.dark ? 0.92 : 0.85),
        borderRadius: BorderRadius.circular(r),
        border: Border.all(color: p.edge, width: 1), boxShadow: p.raisedSm);
  }
  static BoxDecoration scrim(BuildContext c, {double r = XlRadius.lg}) {
    final p = XlPalette.of(c);
    return BoxDecoration(color: p.scrim, borderRadius: BorderRadius.circular(r));
  }
  static BoxDecoration accent(BuildContext c, {double r = XlRadius.lg}) {
    final p = XlPalette.of(c);
    return BoxDecoration(gradient: p.face, borderRadius: BorderRadius.circular(r),
        border: Border.all(color: p.pink.withOpacity(0.35), width: 1.4),
        boxShadow: [...p.raised, BoxShadow(color: p.pink.withOpacity(p.dark ? 0.28 : 0.18),
            blurRadius: 26, spreadRadius: -6)]);
  }
  static BoxDecoration accentSoft(BuildContext c, {double r = XlRadius.lg}) {
    final p = XlPalette.of(c);
    return BoxDecoration(gradient: p.face, borderRadius: BorderRadius.circular(r),
        border: Border.all(color: p.pink.withOpacity(0.22), width: 1.2),
        boxShadow: [...p.raisedSm, BoxShadow(color: p.pink.withOpacity(p.dark ? 0.18 : 0.12),
            blurRadius: 20, spreadRadius: -5)]);
  }
  static BoxDecoration gold(BuildContext c, {double r = XlRadius.lg}) {
    final p = XlPalette.of(c);
    return BoxDecoration(gradient: p.face, borderRadius: BorderRadius.circular(r),
        border: Border.all(color: p.gold.withOpacity(0.4), width: 1.4),
        boxShadow: [...p.raised, BoxShadow(color: p.gold.withOpacity(p.dark ? 0.30 : 0.20),
            blurRadius: 26, spreadRadius: -6)]);
  }
  static BoxDecoration green(BuildContext c, {double r = XlRadius.lg}) {
    final p = XlPalette.of(c);
    return BoxDecoration(gradient: p.face, borderRadius: BorderRadius.circular(r),
        border: Border.all(color: p.green.withOpacity(0.4), width: 1.4),
        boxShadow: [...p.raised, BoxShadow(color: p.green.withOpacity(p.dark ? 0.30 : 0.20),
            blurRadius: 26, spreadRadius: -6)]);
  }
  static BoxDecoration violet(BuildContext c, {double r = XlRadius.lg}) {
    final p = XlPalette.of(c);
    return BoxDecoration(gradient: p.face, borderRadius: BorderRadius.circular(r),
        border: Border.all(color: p.violet.withOpacity(0.4), width: 1.4),
        boxShadow: [...p.raised, BoxShadow(color: p.violet.withOpacity(p.dark ? 0.30 : 0.20),
            blurRadius: 26, spreadRadius: -6)]);
  }
  static BoxDecoration red(BuildContext c, {double r = XlRadius.lg}) {
    final p = XlPalette.of(c);
    return BoxDecoration(gradient: p.face, borderRadius: BorderRadius.circular(r),
        border: Border.all(color: p.red.withOpacity(0.4), width: 1.4),
        boxShadow: [...p.raised, BoxShadow(color: p.red.withOpacity(p.dark ? 0.30 : 0.20),
            blurRadius: 26, spreadRadius: -6)]);
  }
  static BoxDecoration brand(BuildContext c, {double r = XlRadius.lg}) {
    final p = XlPalette.of(c);
    return BoxDecoration(gradient: p.gradBrand, borderRadius: BorderRadius.circular(r),
        border: Border.all(color: Colors.white.withOpacity(p.dark ? 0.35 : 0.5), width: 1),
        boxShadow: p.raisedSm);
  }
  static BoxDecoration brandV(BuildContext c, {double r = XlRadius.lg}) {
    final p = XlPalette.of(c);
    return BoxDecoration(gradient: p.gradBrandV, borderRadius: BorderRadius.circular(r),
        border: Border.all(color: Colors.white.withOpacity(p.dark ? 0.35 : 0.5), width: 1),
        boxShadow: p.raisedSm);
  }
  static BoxDecoration goldFill(BuildContext c, {double r = XlRadius.lg}) {
    final p = XlPalette.of(c);
    return BoxDecoration(gradient: p.gradGold, borderRadius: BorderRadius.circular(r),
        border: Border.all(color: Colors.white.withOpacity(p.dark ? 0.30 : 0.45), width: 1),
        boxShadow: p.raisedSm);
  }
  static BoxDecoration greenFill(BuildContext c, {double r = XlRadius.lg}) {
    final p = XlPalette.of(c);
    return BoxDecoration(gradient: p.gradGreen, borderRadius: BorderRadius.circular(r),
        border: Border.all(color: Colors.white.withOpacity(p.dark ? 0.30 : 0.45), width: 1),
        boxShadow: p.raisedSm);
  }
  static BoxDecoration glowDot(Color color, {double size = 8}) => BoxDecoration(
    color: color, shape: BoxShape.circle,
    boxShadow: [BoxShadow(color: color.withOpacity(0.6), blurRadius: size * 1.5, spreadRadius: -1)]);
  static BoxDecoration glowDotLg(Color color, {double size = 10}) => BoxDecoration(
    color: color, shape: BoxShape.circle,
    boxShadow: [BoxShadow(color: color.withOpacity(0.7), blurRadius: size * 2, spreadRadius: -1)]);
  static BoxDecoration brandOrb(BuildContext c, {double size = 44}) {
    final p = XlPalette.of(c);
    return BoxDecoration(gradient: p.gradBrand, shape: BoxShape.circle,
        border: Border.all(color: Colors.white.withOpacity(p.dark ? 0.35 : 0.5), width: 2),
        boxShadow: [...p.raisedSm, BoxShadow(color: p.pink.withOpacity(0.4), blurRadius: 22, spreadRadius: -4)]);
  }
  static BoxDecoration brandOrbLg(BuildContext c, {double size = 60}) {
    final p = XlPalette.of(c);
    return BoxDecoration(gradient: p.gradBrand, shape: BoxShape.circle,
        border: Border.all(color: Colors.white.withOpacity(p.dark ? 0.40 : 0.55), width: 3),
        boxShadow: [...p.raised, BoxShadow(color: p.pink.withOpacity(0.5), blurRadius: 30, spreadRadius: -6)]);
  }
  static BoxDecoration orb(BuildContext c, {double size = 44, Color? color}) {
    final p = XlPalette.of(c);
    final cc = color ?? p.pink;
    return BoxDecoration(
      gradient: RadialGradient(colors: [cc.withOpacity(0.9), cc.withOpacity(0.6), cc.withOpacity(0.2)]),
      shape: BoxShape.circle,
      border: Border.all(color: Colors.white.withOpacity(p.dark ? 0.20 : 0.40), width: 1),
      boxShadow: [...p.raisedSm, BoxShadow(color: cc.withOpacity(0.35), blurRadius: 24, spreadRadius: -4)]);
  }
  static Widget aurora(BuildContext c, {required Widget child}) {
    final p = XlPalette.of(c);
    return Stack(fit: StackFit.expand, children: [
      Container(color: p.bg),
      Positioned(top: -140, left: -120, child: _blob(p.glow1, 460)),
      Positioned(top: 40, right: -140, child: _blob(p.glow2, 380)),
      Positioned(bottom: -160, left: 100, child: _blob(p.glow3, 500)),
      Positioned(bottom: 120, right: -80, child: _blob(p.glow4, 320)),
      Positioned(top: 200, left: 180, child: _blob(p.glow5, 260)),
      child,
    ]);
  }
  static Widget _blob(Color c, double size) => IgnorePointer(child: Container(
    width: size, height: size,
    decoration: BoxDecoration(shape: BoxShape.circle,
        gradient: RadialGradient(colors: [c, c.withOpacity(0)]))));
  static Widget divider(BuildContext c, {double height = 1, double inset = 0}) {
    final p = XlPalette.of(c);
    return Padding(padding: EdgeInsets.symmetric(horizontal: inset),
        child: Container(height: height, decoration: BoxDecoration(
            gradient: p.dividerGrad, borderRadius: BorderRadius.circular(height))));
  }
  static Widget chip(BuildContext c, String text, {Color? color, IconData? icon}) {
    final p = XlPalette.of(c);
    final cc = color ?? p.pink;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: cc.withOpacity(p.dark ? 0.14 : 0.10),
        borderRadius: BorderRadius.circular(XlRadius.pill),
        border: Border.all(color: cc.withOpacity(0.28), width: 1),
      ),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        if (icon != null) ...[Icon(icon, size: 12, color: cc), const SizedBox(width: 6)],
        Text(text, style: TextStyle(fontSize: XlFont.label, fontWeight: FontWeight.w700,
            color: cc, letterSpacing: XlLetterSpacing.wider)),
      ]),
    );
  }
  static Widget badge(BuildContext c, String text, {Color? color}) {
    final p = XlPalette.of(c);
    final cc = color ?? p.pink;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(gradient: LinearGradient(colors: [cc, cc.withOpacity(0.85)]),
          borderRadius: BorderRadius.circular(XlRadius.pill),
          boxShadow: [BoxShadow(color: cc.withOpacity(0.35), blurRadius: 8, spreadRadius: -2)]),
      child: Text(text, style: TextStyle(fontSize: XlFont.labelSm, fontWeight: FontWeight.w800,
          color: p.dark ? p.btnInk : Colors.white, letterSpacing: XlLetterSpacing.wider)),
    );
  }
  static Widget statusDot(Color color, {double size = 8, bool glow = true}) => Container(
    width: size, height: size,
    decoration: BoxDecoration(color: color, shape: BoxShape.circle,
        boxShadow: glow ? [BoxShadow(color: color.withOpacity(0.6),
            blurRadius: size * 1.6, spreadRadius: -1)] : null));
}

extension XlContext on BuildContext {
  XlPalette get xl => XlPalette.of(this);
  bool get isDark => xl.dark;
  bool get isLight => !xl.dark;
  bool get isMobile => MediaQuery.of(this).size.width < XlBreakpoint.mobile;
  bool get isTablet => MediaQuery.of(this).size.width < XlBreakpoint.desktopSm;
  bool get isDesktop => MediaQuery.of(this).size.width >= XlBreakpoint.desktopSm;
  double get screenW => MediaQuery.of(this).size.width;
  double get screenH => MediaQuery.of(this).size.height;
  EdgeInsets get viewInsets => MediaQuery.of(this).viewInsets;
  EdgeInsets get viewPadding => MediaQuery.of(this).viewPadding;
}

extension XlTextStyle on TextStyle {
  TextStyle get tabular => copyWith(fontFeatures: const [FontFeature.tabularFigures()]);
  TextStyle withColor(Color c) => copyWith(color: c);
  TextStyle withSize(double s) => copyWith(fontSize: s);
  TextStyle withWeight(FontWeight w) => copyWith(fontWeight: w);
  TextStyle withHeight(double h) => copyWith(height: h);
  TextStyle withSpacing(double s) => copyWith(letterSpacing: s);
  TextStyle get bold => copyWith(fontWeight: FontWeight.w700);
  TextStyle get extrabold => copyWith(fontWeight: FontWeight.w800);
  TextStyle get semibold => copyWith(fontWeight: FontWeight.w600);
  TextStyle get medium => copyWith(fontWeight: FontWeight.w500);
}

extension XlWidget on Widget {
  Widget padAll(double v) => Padding(padding: EdgeInsets.all(v), child: this);
  Widget padH(double v) => Padding(padding: EdgeInsets.symmetric(horizontal: v), child: this);
  Widget padV(double v) => Padding(padding: EdgeInsets.symmetric(vertical: v), child: this);
  Widget pad(EdgeInsets e) => Padding(padding: e, child: this);
  Widget opacity(double o) => Opacity(opacity: o, child: this);
  Widget get visible => Visibility(visible: true, child: this);
  Widget get hidden => Visibility(visible: false, child: this);
}