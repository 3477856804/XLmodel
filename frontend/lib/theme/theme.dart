import 'dart:ui';
import 'package:flutter/material.dart';
import 'dart:io' show Platform;
import 'theme_controller.dart';
import 'typography.dart';

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
  /// 提高对比度变体。
  ///
  /// HIG《Color》明确要求：自定义色必须同时提供 light / dark /
  /// increased contrast 三套上下文，且高对比档要「明显更高的视觉区分度」。
  /// 以前只有前两套，而且 theme_controller 里那个 _increasedContrast
  /// 字段从没被读过或写过 —— 现在由 XlPalette.of() 读取系统的
  /// AccessibilityFeatures.highContrast 来选变体。
  final bool hc;
  final bool isDark;
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
  final Gradient screenGlow;
  final Gradient screenGlowPink;
  final Gradient screenGlowGold;
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
    this.hc = false,
    required this.isDark,
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
    hc: false,
    isDark: true,
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
    text4: Color(0xFF908493),
    decor: Color(0xFF928396),
    decorSoft: Color(0xFF6D6171),
    pink: Color(0xFFFF5580),
    pink2: Color(0xFFFF8AC4),
    pink3: Color(0xFFFFC4DA),
    pinkSoft: Color(0x33FF5580),
    gold: Color(0xFFE8C46A),
    gold2: Color(0xFFF7E3A8),
    gold3: Color(0xFFFFF6DC),
    goldSoft: Color(0x33E8C46A),
    violet: Color(0xFF6D7CFF),
    violet2: Color(0xFFA7AAFF),
    violet3: Color(0xFFCDD6FF),
    green: Color(0xFF30D158),
    green2: Color(0xFF8CE8A8),
    green3: Color(0xFFCBEFD6),
    red: Color(0xFFFF4245),
    red2: Color(0xFFFF6165),
    blue: Color(0xFF0091FF),
    blue2: Color(0xFF5CB8FF),
    orange: Color(0xFFFF9230),
    orange2: Color(0xFFFFA056),
    cyan: Color(0xFF3CD3FE),
    cyan2: Color(0xFF6DD9FF),
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
    ripple: Color(0x40FF5580),
    rippleSoft: Color(0x26FF5580),
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
      colors: [Color(0xFFFF5580), Color(0xFFFF7FAE), Color(0xFFE8C46A)],
      stops: [0.0, 0.45, 1.0],
    ),
    gradBrandH: LinearGradient(
      begin: Alignment.centerLeft,
      end: Alignment.centerRight,
      colors: [Color(0xFFFF5580), Color(0xFFFF7FAE), Color(0xFFE8C46A)],
      stops: [0.0, 0.5, 1.0],
    ),
    gradBrandV: LinearGradient(
      begin: Alignment.topCenter,
      end: Alignment.bottomCenter,
      colors: [Color(0xFFFF7FAE), Color(0xFFFF5580), Color(0xFFE8C46A)],
      stops: [0.0, 0.55, 1.0],
    ),
    gradText: LinearGradient(
      colors: [
        Color(0xFFFFC4DA),
        Color(0xFFFF6A9C),
        Color(0xFFF7E3A8),
        Color(0xFFFFB0CC)
      ],
      stops: [0.0, 0.35, 0.7, 1.0],
    ),
    gradTextH: LinearGradient(
      begin: Alignment.centerLeft,
      end: Alignment.centerRight,
      colors: [Color(0xFFFFC4DA), Color(0xFFFF6A9C), Color(0xFFF7E3A8)],
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
      colors: [Color(0xFF30D158), Color(0xFF8CE8A8)],
    ),
    gradViolet: LinearGradient(
      colors: [Color(0xFF6D7CFF), Color(0xFFA7AAFF)],
    ),
    gradRed: LinearGradient(
      colors: [Color(0xFFFF4245), Color(0xFFFF6165)],
    ),
    gradBlue: LinearGradient(
      colors: [Color(0xFF0091FF), Color(0xFF5CB8FF)],
    ),
    gradCyan: LinearGradient(
      colors: [Color(0xFF3CD3FE), Color(0xFF6DD9FF)],
    ),
    gradSunset: LinearGradient(
      colors: [Color(0xFFFF9230), Color(0xFFFF5580), Color(0xFF6D7CFF)],
      stops: [0.0, 0.5, 1.0],
    ),
    gradOcean: LinearGradient(
      colors: [Color(0xFF3CD3FE), Color(0xFF0091FF), Color(0xFF6D7CFF)],
      stops: [0.0, 0.5, 1.0],
    ),
    btnFace: LinearGradient(
      colors: [Color(0xFFFF5580), Color(0xFFFF7FAE), Color(0xFFE8C46A)],
      stops: [0.0, 0.45, 1.0],
    ),
    btnFaceV: LinearGradient(
      begin: Alignment.topCenter,
      end: Alignment.bottomCenter,
      colors: [Color(0xFFFF7FAE), Color(0xFFFF5580), Color(0xFFE8C46A)],
      stops: [0.0, 0.55, 1.0],
    ),
    btnFacePressed: LinearGradient(
      colors: [Color(0xFFE04A76), Color(0xFFF0A8C8), Color(0xFFDDBE6E)],
      stops: [0.0, 0.45, 1.0],
    ),
    btnFaceGhost: LinearGradient(
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
      colors: [Color(0x14FFFFFF), Color(0x08FFFFFF)],
    ),
    screenGlow: RadialGradient(
      colors: [Color(0x1AFF5580), Color(0x00000000)],
    ),
    screenGlowPink: RadialGradient(
      colors: [Color(0x40FF5580), Color(0x00000000)],
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
      colors: [Color(0x1AFF5580), Color(0x0DE8C46A)],
    ),
    cardGold: LinearGradient(
      colors: [Color(0x1AE8C46A), Color(0x0DE8C46A)],
    ),
    cardGreen: LinearGradient(
      colors: [Color(0x1A30D158), Color(0x0D30D158)],
    ),
    cardViolet: LinearGradient(
      colors: [Color(0x1A6D7CFF), Color(0x0D6D7CFF)],
    ),
    dividerGrad: LinearGradient(
      colors: [Color(0x00FFFFFF), Color(0x14FFFFFF), Color(0x00FFFFFF)],
      stops: [0.0, 0.5, 1.0],
    ),
    shimmer: LinearGradient(
      colors: [Color(0x00FFFFFF), Color(0x26FFFFFF), Color(0x00FFFFFF)],
      stops: [0.0, 0.5, 1.0],
    ),
    glow1: Color(0x14FF5580),
    glow2: Color(0x0DE8C46A),
    glow3: Color(0x0D6D7CFF),
    glow4: Color(0x0A30D158),
    glow5: Color(0x080091FF),
    noiseOpacity: 0.03,
  );

  static const darkHc = XlPalette(
    hc: true,
    isDark: true,
    bg: Color(0xFF17131D),
    bgSoft: Color(0xFF1A1520),
    bgDeep: Color(0xFF0F0B14),
    surface: Color(0xFF1C1724),
    surfaceHi: Color(0xFF241C2E),
    surfaceLo: Color(0xFF161119),
    surfaceAlt: Color(0xFF201926),
    screen: Color(0xFF120E18),
    screenSoft: Color(0xFF16111C),
    edge: Color(0x1BFFFFFF),
    edgeStrong: Color(0x31FFFFFF),
    edgeSoft: Color(0x0FFFFFFF),
    text1: Color(0xFFFFFFFF),
    text2: Color(0xFFD6CBD8),
    text3: Color(0xFFC0B4C2),
    text4: Color(0xFFACA0AE),
    decor: Color(0xFFB4A5B8),
    decorSoft: Color(0xFFACA0AE),
    pink: Color(0xFFFF8AC4),
    pink2: Color(0xFFFFC4DA),
    pink3: Color(0xFFFFE2EC),
    pinkSoft: Color(0x4AFF8AC4),
    gold: Color(0xFFF2D98F),
    gold2: Color(0xFFFBEEC9),
    gold3: Color(0xFFFFF6DC),
    goldSoft: Color(0x4AF2D98F),
    violet: Color(0xFFA7AAFF),
    violet2: Color(0xFFCDD6FF),
    violet3: Color(0xFFE6EAFF),
    green: Color(0xFF4AD968),
    green2: Color(0xFFA8F0C0),
    green3: Color(0xFFDFF5E6),
    red: Color(0xFFFF6165),
    red2: Color(0xFFFF8A8D),
    blue: Color(0xFF5CB8FF),
    blue2: Color(0xFF8ED1FF),
    orange: Color(0xFFFFA056),
    orange2: Color(0xFFFFC08D),
    cyan: Color(0xFF6DD9FF),
    cyan2: Color(0xFFA0E8FF),
    shDark: Color(0x8C000000),
    shDarker: Color(0xA6000000),
    shDarkest: Color(0xC4000000),
    shLight: Color(0x15FFFFFF),
    shLighter: Color(0x26FFFFFF),
    shLighter2: Color(0x3BFFFFFF),
    shDeep: Color(0xB3000000),
    shDeep2: Color(0xD9000000),
    btnInk: Color(0xFF1E0910),
    btnInk2: Color(0xFF2E0F1C),
    btnHi: Color(0x80FFFFFF),
    btnHi2: Color(0x80FFFFFF),
    ripple: Color(0x5DFF8AC4),
    rippleSoft: Color(0x48FF8AC4),
    divider: Color(0x26FFFFFF),
    dividerStrong: Color(0x48FFFFFF),
    dividerSoft: Color(0x13FFFFFF),
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
      colors: [Color(0xFFFF8AC4), Color(0xFFFFB0CC), Color(0xFFF2D98F)],
      stops: [0.0, 0.45, 1.0],
    ),
    gradBrandH: LinearGradient(
      begin: Alignment.centerLeft,
      end: Alignment.centerRight,
      colors: [Color(0xFFFF8AC4), Color(0xFFFFB0CC), Color(0xFFF2D98F)],
      stops: [0.0, 0.5, 1.0],
    ),
    gradBrandV: LinearGradient(
      begin: Alignment.topCenter,
      end: Alignment.bottomCenter,
      colors: [Color(0xFFFFB0CC), Color(0xFFFF8AC4), Color(0xFFF2D98F)],
      stops: [0.0, 0.55, 1.0],
    ),
    gradText: LinearGradient(
      colors: [
        Color(0xFFFFE2EC),
        Color(0xFFFF6A9C),
        Color(0xFFFBEEC9),
        Color(0xFFFFB0CC)
      ],
      stops: [0.0, 0.35, 0.7, 1.0],
    ),
    gradTextH: LinearGradient(
      begin: Alignment.centerLeft,
      end: Alignment.centerRight,
      colors: [Color(0xFFFFE2EC), Color(0xFFFF6A9C), Color(0xFFFBEEC9)],
      stops: [0.0, 0.5, 1.0],
    ),
    gradGold: LinearGradient(
      colors: [Color(0xFFF2D98F), Color(0xFFFBEEC9), Color(0xFFF2D98F)],
      stops: [0.0, 0.5, 1.0],
    ),
    gradGoldSoft: LinearGradient(
      colors: [Color(0x80F2D98F), Color(0x4AF2D98F)],
    ),
    gradGreen: LinearGradient(
      colors: [Color(0xFF4AD968), Color(0xFFA8F0C0)],
    ),
    gradViolet: LinearGradient(
      colors: [Color(0xFFA7AAFF), Color(0xFFCDD6FF)],
    ),
    gradRed: LinearGradient(
      colors: [Color(0xFFFF6165), Color(0xFFFF8A8D)],
    ),
    gradBlue: LinearGradient(
      colors: [Color(0xFF5CB8FF), Color(0xFF8ED1FF)],
    ),
    gradCyan: LinearGradient(
      colors: [Color(0xFF6DD9FF), Color(0xFFA0E8FF)],
    ),
    gradSunset: LinearGradient(
      colors: [Color(0xFFFFA056), Color(0xFFFF8AC4), Color(0xFFA7AAFF)],
      stops: [0.0, 0.5, 1.0],
    ),
    gradOcean: LinearGradient(
      colors: [Color(0xFF6DD9FF), Color(0xFF5CB8FF), Color(0xFFA7AAFF)],
      stops: [0.0, 0.5, 1.0],
    ),
    btnFace: LinearGradient(
      colors: [Color(0xFFFF8AC4), Color(0xFFFFB0CC), Color(0xFFF2D98F)],
      stops: [0.0, 0.45, 1.0],
    ),
    btnFaceV: LinearGradient(
      begin: Alignment.topCenter,
      end: Alignment.bottomCenter,
      colors: [Color(0xFFFFB0CC), Color(0xFFFF8AC4), Color(0xFFF2D98F)],
      stops: [0.0, 0.55, 1.0],
    ),
    btnFacePressed: LinearGradient(
      colors: [Color(0xFFFF8AC4), Color(0xFFFFC4DA), Color(0xFFF2D98F)],
      stops: [0.0, 0.45, 1.0],
    ),
    btnFaceGhost: LinearGradient(
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
      colors: [Color(0x26FFFFFF), Color(0x0FFFFFFF)],
    ),
    screenGlow: RadialGradient(
      colors: [Color(0x31FF8AC4), Color(0x00000000)],
    ),
    screenGlowPink: RadialGradient(
      colors: [Color(0x5DFF8AC4), Color(0x00000000)],
    ),
    screenGlowGold: RadialGradient(
      colors: [Color(0x4AF2D98F), Color(0x00000000)],
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
      colors: [Color(0x31FF8AC4), Color(0x19F2D98F)],
    ),
    cardGold: LinearGradient(
      colors: [Color(0x31F2D98F), Color(0x19F2D98F)],
    ),
    cardGreen: LinearGradient(
      colors: [Color(0x314AD968), Color(0x194AD968)],
    ),
    cardViolet: LinearGradient(
      colors: [Color(0x31A7AAFF), Color(0x19A7AAFF)],
    ),
    dividerGrad: LinearGradient(
      colors: [Color(0x00FFFFFF), Color(0x26FFFFFF), Color(0x00FFFFFF)],
      stops: [0.0, 0.5, 1.0],
    ),
    shimmer: LinearGradient(
      colors: [Color(0x00FFFFFF), Color(0x48FFFFFF), Color(0x00FFFFFF)],
      stops: [0.0, 0.5, 1.0],
    ),
    glow1: Color(0x26FF8AC4),
    glow2: Color(0x19F2D98F),
    glow3: Color(0x19A7AAFF),
    glow4: Color(0x134AD968),
    glow5: Color(0x0F5CB8FF),
    noiseOpacity: 0.03,
  );

  static const light = XlPalette(
    hc: false,
    isDark: false,
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
    text2: Color(0xFF4A3F51),
    text3: Color(0xFF615669),
    text4: Color(0xFF665B6D),
    decor: Color(0xFF665B6D),
    decorSoft: Color(0xFF867B8C),
    pink: Color(0xFFB6203D),
    pink2: Color(0xFF9F1C35),
    pink3: Color(0xFF84172C),
    pinkSoft: Color(0x33C12240),
    gold: Color(0xFF795A14),
    gold2: Color(0xFF694E12),
    gold3: Color(0xFF56400E),
    goldSoft: Color(0x337F5F15),
    violet: Color(0xFF534AD2),
    violet2: Color(0xFF4940B8),
    violet3: Color(0xFF3C3597),
    green: Color(0xFF1D6D31),
    green2: Color(0xFF195E2A),
    green3: Color(0xFF154E23),
    red: Color(0xFFB4282B),
    red2: Color(0xFF9D2325),
    blue: Color(0xFF005FB2),
    blue2: Color(0xFF00529B),
    orange: Color(0xFF8F4E17),
    orange2: Color(0xFF7C4413),
    cyan: Color(0xFF00687E),
    cyan2: Color(0xFF005A6D),
    shDark: Color(0x4D5D4A72),
    shDarker: Color(0x665D4A72),
    shDarkest: Color(0x805D4A72),
    shLight: Color(0xF2FFFFFF),
    shLighter: Color(0xFFFFFFFF),
    shLighter2: Color(0xFFFFFFFF),
    shDeep: Color(0x805D4A72),
    shDeep2: Color(0x995D4A72),
    btnInk: Color(0xFFFFFFFF),
    btnInk2: Color(0xFFFFF2F6),
    btnHi: Color(0x33FFFFFF),
    btnHi2: Color(0x59FFFFFF),
    ripple: Color(0x30C12240),
    rippleSoft: Color(0x1FC12240),
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
      colors: [Color(0xFFB6203D), Color(0xFF9F1C35), Color(0xFF795A14)],
      stops: [0.0, 0.45, 1.0],
    ),
    gradBrandH: LinearGradient(
      begin: Alignment.centerLeft,
      end: Alignment.centerRight,
      colors: [Color(0xFFB6203D), Color(0xFF9F1C35), Color(0xFF795A14)],
      stops: [0.0, 0.5, 1.0],
    ),
    gradBrandV: LinearGradient(
      begin: Alignment.topCenter,
      end: Alignment.bottomCenter,
      colors: [Color(0xFF9F1C35), Color(0xFFB6203D), Color(0xFF795A14)],
      stops: [0.0, 0.55, 1.0],
    ),
    gradText: LinearGradient(
      colors: [Color(0xFF9F1C35), Color(0xFFB6203D), Color(0xFF795A14)],
      stops: [0.0, 0.4, 1.0],
    ),
    gradTextH: LinearGradient(
      begin: Alignment.centerLeft,
      end: Alignment.centerRight,
      colors: [Color(0xFF9F1C35), Color(0xFFB6203D), Color(0xFF795A14)],
      stops: [0.0, 0.5, 1.0],
    ),
    gradGold: LinearGradient(
      colors: [Color(0xFF795A14), Color(0xFF694E12), Color(0xFF795A14)],
      stops: [0.0, 0.5, 1.0],
    ),
    gradGoldSoft: LinearGradient(
      colors: [Color(0x407F5F15), Color(0x267F5F15)],
    ),
    gradGreen: LinearGradient(
      colors: [Color(0xFF1D6D31), Color(0xFF195E2A)],
    ),
    gradViolet: LinearGradient(
      colors: [Color(0xFF534AD2), Color(0xFF4940B8)],
    ),
    gradRed: LinearGradient(
      colors: [Color(0xFFB4282B), Color(0xFF9D2325)],
    ),
    gradBlue: LinearGradient(
      colors: [Color(0xFF005FB2), Color(0xFF00529B)],
    ),
    gradCyan: LinearGradient(
      colors: [Color(0xFF00687E), Color(0xFF005A6D)],
    ),
    gradSunset: LinearGradient(
      colors: [Color(0xFF8F4E17), Color(0xFFB6203D), Color(0xFF534AD2)],
      stops: [0.0, 0.5, 1.0],
    ),
    gradOcean: LinearGradient(
      colors: [Color(0xFF00687E), Color(0xFF005FB2), Color(0xFF534AD2)],
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
      colors: [Color(0x1AC12240), Color(0x00000000)],
    ),
    screenGlowPink: RadialGradient(
      colors: [Color(0x33C12240), Color(0x00000000)],
    ),
    screenGlowGold: RadialGradient(
      colors: [Color(0x337F5F15), Color(0x00000000)],
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
      colors: [Color(0x1AC12240), Color(0x0D7F5F15)],
    ),
    cardGold: LinearGradient(
      colors: [Color(0x1A7F5F15), Color(0x0D7F5F15)],
    ),
    cardGreen: LinearGradient(
      colors: [Color(0x1A1E7334), Color(0x0D1E7334)],
    ),
    cardViolet: LinearGradient(
      colors: [Color(0x1A584EDF), Color(0x0D584EDF)],
    ),
    dividerGrad: LinearGradient(
      colors: [Color(0x005D4A72), Color(0x1A5D4A72), Color(0x005D4A72)],
      stops: [0.0, 0.5, 1.0],
    ),
    shimmer: LinearGradient(
      colors: [Color(0x00FFFFFF), Color(0x80FFFFFF), Color(0x00FFFFFF)],
      stops: [0.0, 0.5, 1.0],
    ),
    glow1: Color(0x1AC12240),
    glow2: Color(0x1F7F5F15),
    glow3: Color(0x14584EDF),
    glow4: Color(0x141E7334),
    glow5: Color(0x140064BC),
    noiseOpacity: 0.025,
  );

  static const lightHc = XlPalette(
    hc: true,
    isDark: false,
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
    text1: Color(0xFF1A1220),
    text2: Color(0xFF3A3141),
    text3: Color(0xFF463C4C),
    text4: Color(0xFF524659),
    decor: Color(0xFF4E4456),
    decorSoft: Color(0xFF615669),
    pink: Color(0xFF8D192F),
    pink2: Color(0xFF84172C),
    pink3: Color(0xFF751326),
    pinkSoft: Color(0x4A8D192F),
    gold: Color(0xFF56400E),
    gold2: Color(0xFF56400E),
    gold3: Color(0xFF48360C),
    goldSoft: Color(0x4A56400E),
    violet: Color(0xFF3C3597),
    violet2: Color(0xFF3C3597),
    violet3: Color(0xFF332D80),
    green: Color(0xFF154E23),
    green2: Color(0xFF154E23),
    green3: Color(0xFF113F1D),
    red: Color(0xFF8B1E21),
    red2: Color(0xFF821D1F),
    blue: Color(0xFF004480),
    blue2: Color(0xFF004480),
    orange: Color(0xFF6D3C11),
    orange2: Color(0xFF663810),
    cyan: Color(0xFF004A5A),
    cyan2: Color(0xFF004A5A),
    shDark: Color(0x705D4A72),
    shDarker: Color(0x665D4A72),
    shDarkest: Color(0x805D4A72),
    shLight: Color(0xF2FFFFFF),
    shLighter: Color(0xFFFFFFFF),
    shLighter2: Color(0xFFFFFFFF),
    shDeep: Color(0x805D4A72),
    shDeep2: Color(0x995D4A72),
    btnInk: Color(0xFFFFFFFF),
    btnInk2: Color(0xFFFFFFFF),
    btnHi: Color(0x4AFFFFFF),
    btnHi2: Color(0x80FFFFFF),
    ripple: Color(0x468D192F),
    rippleSoft: Color(0x3B8D192F),
    divider: Color(0x315D4A72),
    dividerStrong: Color(0x4A5D4A72),
    dividerSoft: Color(0x195D4A72),
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
      colors: [Color(0xFF8D192F), Color(0xFF84172C), Color(0xFF56400E)],
      stops: [0.0, 0.45, 1.0],
    ),
    gradBrandH: LinearGradient(
      begin: Alignment.centerLeft,
      end: Alignment.centerRight,
      colors: [Color(0xFF8D192F), Color(0xFF84172C), Color(0xFF56400E)],
      stops: [0.0, 0.5, 1.0],
    ),
    gradBrandV: LinearGradient(
      begin: Alignment.topCenter,
      end: Alignment.bottomCenter,
      colors: [Color(0xFF84172C), Color(0xFF8D192F), Color(0xFF56400E)],
      stops: [0.0, 0.55, 1.0],
    ),
    gradText: LinearGradient(
      colors: [Color(0xFF84172C), Color(0xFF8D192F), Color(0xFF56400E)],
      stops: [0.0, 0.4, 1.0],
    ),
    gradTextH: LinearGradient(
      begin: Alignment.centerLeft,
      end: Alignment.centerRight,
      colors: [Color(0xFF84172C), Color(0xFF8D192F), Color(0xFF56400E)],
      stops: [0.0, 0.5, 1.0],
    ),
    gradGold: LinearGradient(
      colors: [Color(0xFF56400E), Color(0xFF56400E), Color(0xFF56400E)],
      stops: [0.0, 0.5, 1.0],
    ),
    gradGoldSoft: LinearGradient(
      colors: [Color(0x5D56400E), Color(0x4856400E)],
    ),
    gradGreen: LinearGradient(
      colors: [Color(0xFF154E23), Color(0xFF154E23)],
    ),
    gradViolet: LinearGradient(
      colors: [Color(0xFF3C3597), Color(0xFF3C3597)],
    ),
    gradRed: LinearGradient(
      colors: [Color(0xFF8B1E21), Color(0xFF821D1F)],
    ),
    gradBlue: LinearGradient(
      colors: [Color(0xFF004480), Color(0xFF004480)],
    ),
    gradCyan: LinearGradient(
      colors: [Color(0xFF004A5A), Color(0xFF004A5A)],
    ),
    gradSunset: LinearGradient(
      colors: [Color(0xFF6D3C11), Color(0xFF8D192F), Color(0xFF3C3597)],
      stops: [0.0, 0.5, 1.0],
    ),
    gradOcean: LinearGradient(
      colors: [Color(0xFF004A5A), Color(0xFF004480), Color(0xFF3C3597)],
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
      colors: [Color(0x195D4A72), Color(0x0A5D4A72)],
    ),
    screenGlow: RadialGradient(
      colors: [Color(0x318D192F), Color(0x00000000)],
    ),
    screenGlowPink: RadialGradient(
      colors: [Color(0x4A8D192F), Color(0x00000000)],
    ),
    screenGlowGold: RadialGradient(
      colors: [Color(0x4A56400E), Color(0x00000000)],
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
      colors: [Color(0x318D192F), Color(0x1956400E)],
    ),
    cardGold: LinearGradient(
      colors: [Color(0x3156400E), Color(0x1956400E)],
    ),
    cardGreen: LinearGradient(
      colors: [Color(0x31154E23), Color(0x19154E23)],
    ),
    cardViolet: LinearGradient(
      colors: [Color(0x313C3597), Color(0x193C3597)],
    ),
    dividerGrad: LinearGradient(
      colors: [Color(0x005D4A72), Color(0x315D4A72), Color(0x005D4A72)],
      stops: [0.0, 0.5, 1.0],
    ),
    shimmer: LinearGradient(
      colors: [Color(0x00FFFFFF), Color(0x80FFFFFF), Color(0x00FFFFFF)],
      stops: [0.0, 0.5, 1.0],
    ),
    glow1: Color(0x318D192F),
    glow2: Color(0x3B56400E),
    glow3: Color(0x263C3597),
    glow4: Color(0x26154E23),
    glow5: Color(0x26004480),
    noiseOpacity: 0.025,
  );

  /// 当前上下文对应的调色板。
  ///
  /// 按 HIG《Color》的要求补上 increased-contrast 一档：系统开了
  /// 「提高对比度」时走 darkHc / lightHc（同色相、更高饱和度与对比度、
  /// 半透明装饰层整体加厚），没开就走 dark / light。
  ///
  /// 注意这里刻意**不**依赖 BuildContext 的继承链：四个变体是 const，
  /// 用 MediaQuery.of(context).platformDispatcher.accessibilityFeatures
  /// 直接取当前值，Theme 重建时自然跟着换，不用往 Widget 树里再塞一层。
  static XlPalette of(BuildContext c) {
    final ext = Theme.of(c).extension<XlPalette>();
    final hc = effectiveHighContrast(c);
    if (ext == null) return resolve(true, hc: hc);
    // ThemeData 还没跟着重建的那一帧，直接换成同明暗的对档，
    // 避免新旧配色混用。
    if (ext.hc == hc) return ext;
    return resolve(ext.isDark, hc: hc);
  }

  /// 当前应当使用高对比配色吗：系统开关 ∨ 设置页的应用内档位。
  ///
  /// 用 maybeHighContrastOf：拿不到 MediaQuery 的极少数调用点（原生窗口
  /// 回调、独立 Overlay）按未开启处理，不能抛异常；同时它会注册依赖，
  /// 系统「提高对比度」一切换，调用方就自动重建。
  static bool effectiveHighContrast(BuildContext c) =>
      XlThemeController.instance
          .resolveHighContrast(MediaQuery.maybeHighContrastOf(c) ?? false);

  /// 供 AppTheme 之外手动构造 ThemeData 的地方（预览卡、错误页）复用。
  static XlPalette resolve(bool isDark, {bool hc = false}) {
    if (hc) return isDark ? XlPalette.darkHc : XlPalette.lightHc;
    return isDark ? XlPalette.dark : XlPalette.light;
  }

  List<BoxShadow> get raisedUltra => [
        BoxShadow(
            color: shDark,
            offset: const Offset(18, 18),
            blurRadius: 36,
            spreadRadius: -4),
        BoxShadow(
            color: shLight,
            offset: const Offset(-18, -18),
            blurRadius: 36,
            spreadRadius: -4),
      ];
  List<BoxShadow> get raisedXxxl => [
        BoxShadow(
            color: shDark,
            offset: const Offset(16, 16),
            blurRadius: 32,
            spreadRadius: -3),
        BoxShadow(
            color: shLight,
            offset: const Offset(-16, -16),
            blurRadius: 32,
            spreadRadius: -3),
      ];
  List<BoxShadow> get raisedXxl => [
        BoxShadow(
            color: shDark,
            offset: const Offset(14, 14),
            blurRadius: 28,
            spreadRadius: -2),
        BoxShadow(
            color: shLight,
            offset: const Offset(-14, -14),
            blurRadius: 28,
            spreadRadius: -2),
      ];
  List<BoxShadow> get raisedXl => [
        BoxShadow(color: shDark, offset: const Offset(12, 12), blurRadius: 24),
        BoxShadow(
            color: shLight, offset: const Offset(-12, -12), blurRadius: 24),
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
  List<BoxShadow> get sunkenXxs => [
        BoxShadow(color: shDark, offset: const Offset(1, 1), blurRadius: 2),
        BoxShadow(color: shLight, offset: const Offset(-1, -1), blurRadius: 2),
      ];
  List<BoxShadow> get sunkenXs => [
        BoxShadow(color: shDark, offset: const Offset(2, 2), blurRadius: 4),
        BoxShadow(color: shLight, offset: const Offset(-2, -2), blurRadius: 4),
      ];
  List<BoxShadow> get sunkenSm => [
        BoxShadow(
            color: shDark,
            offset: const Offset(3, 3),
            blurRadius: 7,
            spreadRadius: -1),
        BoxShadow(
            color: shLight,
            offset: const Offset(-3, -3),
            blurRadius: 7,
            spreadRadius: -1),
      ];
  List<BoxShadow> get sunken => [
        BoxShadow(
            color: shDark,
            offset: const Offset(6, 6),
            blurRadius: 12,
            spreadRadius: -2),
        BoxShadow(
            color: shLight,
            offset: const Offset(-6, -6),
            blurRadius: 12,
            spreadRadius: -2),
      ];
  List<BoxShadow> get sunkenLg => [
        BoxShadow(
            color: shDarker,
            offset: const Offset(8, 8),
            blurRadius: 15,
            spreadRadius: -2),
        BoxShadow(
            color: shLight,
            offset: const Offset(-8, -8),
            blurRadius: 15,
            spreadRadius: -2),
      ];
  List<BoxShadow> get sunkenDeep => [
        BoxShadow(
            color: shDeep,
            offset: const Offset(10, 10),
            blurRadius: 18,
            spreadRadius: -3),
        BoxShadow(
            color: shLight,
            offset: const Offset(-10, -10),
            blurRadius: 18,
            spreadRadius: -3),
      ];
  List<BoxShadow> get sunkenUltra => [
        BoxShadow(
            color: shDeep2,
            offset: const Offset(12, 12),
            blurRadius: 22,
            spreadRadius: -4),
        BoxShadow(
            color: shLight,
            offset: const Offset(-12, -12),
            blurRadius: 22,
            spreadRadius: -4),
      ];
  List<BoxShadow> glowPink({double intensity = 1.0}) => [
        BoxShadow(
            color: pink.withOpacity((isDark ? 0.45 : 0.32) * intensity),
            blurRadius: 24,
            spreadRadius: -4),
      ];
  List<BoxShadow> glowGold({double intensity = 1.0}) => [
        BoxShadow(
            color: gold.withOpacity((isDark ? 0.45 : 0.32) * intensity),
            blurRadius: 24,
            spreadRadius: -4),
      ];
  List<BoxShadow> glowGreen({double intensity = 1.0}) => [
        BoxShadow(
            color: green.withOpacity((isDark ? 0.45 : 0.32) * intensity),
            blurRadius: 24,
            spreadRadius: -4),
      ];
  List<BoxShadow> glowViolet({double intensity = 1.0}) => [
        BoxShadow(
            color: violet.withOpacity((isDark ? 0.45 : 0.32) * intensity),
            blurRadius: 24,
            spreadRadius: -4),
      ];
  List<BoxShadow> glowRed({double intensity = 1.0}) => [
        BoxShadow(
            color: red.withOpacity((isDark ? 0.45 : 0.32) * intensity),
            blurRadius: 24,
            spreadRadius: -4),
      ];
  List<BoxShadow> glowBlue({double intensity = 1.0}) => [
        BoxShadow(
            color: blue.withOpacity((isDark ? 0.45 : 0.32) * intensity),
            blurRadius: 24,
            spreadRadius: -4),
      ];
  List<BoxShadow> glowCyan({double intensity = 1.0}) => [
        BoxShadow(
            color: cyan.withOpacity((isDark ? 0.45 : 0.32) * intensity),
            blurRadius: 24,
            spreadRadius: -4),
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

  /// 语义色 = 调色板里的同名字段。
  ///
  /// 以前这五个是 `static const`，值写死在类里（success 0xFF6BCB77、
  /// warning 0xFFFFD93D、danger 0xFFFF6B6B），和 palette.green /
  /// .orange / .red 是两套不同步的颜色 —— 同一个「成功」在卡片描边和
  /// glowSuccess 里能差出一个色相，正是 HIG 说的「别用同一颜色表达
  /// 不同含义、也别让同一含义有两种颜色」。现在只保留一条来源。
  Color get semanticSuccess => green;
  Color get semanticWarning => orange;
  Color get semanticDanger => red;
  Color get semanticPinkSoft => pink2;
  Color get semanticGoldSoft => gold2;

  List<BoxShadow> get shadowSoft => [
        BoxShadow(
            color: shDark,
            offset: const Offset(2, 2),
            blurRadius: 8,
            spreadRadius: -1),
        BoxShadow(
            color: shLight,
            offset: const Offset(-2, -2),
            blurRadius: 8,
            spreadRadius: -1),
      ];
  List<BoxShadow> get shadowGlow => [
        BoxShadow(
            color: pink.withOpacity(isDark ? 0.40 : 0.28),
            blurRadius: 20,
            spreadRadius: -3),
      ];
  List<BoxShadow> glowSuccess({double intensity = 1.0}) => [
        BoxShadow(
            color:
                semanticSuccess.withOpacity((isDark ? 0.45 : 0.32) * intensity),
            blurRadius: 20,
            spreadRadius: -3),
      ];
  List<BoxShadow> glowWarning({double intensity = 1.0}) => [
        BoxShadow(
            color:
                semanticWarning.withOpacity((isDark ? 0.45 : 0.32) * intensity),
            blurRadius: 20,
            spreadRadius: -3),
      ];
  List<BoxShadow> glowDanger({double intensity = 1.0}) => [
        BoxShadow(
            color:
                semanticDanger.withOpacity((isDark ? 0.45 : 0.32) * intensity),
            blurRadius: 20,
            spreadRadius: -3),
      ];

  @override
  XlPalette copyWith({
    bool? hc,
    bool? dark,
    Color? bg,
    Color? bgSoft,
    Color? bgDeep,
    Color? surface,
    Color? surfaceHi,
    Color? surfaceLo,
    Color? surfaceAlt,
    Color? screen,
    Color? screenSoft,
    Color? edge,
    Color? edgeStrong,
    Color? edgeSoft,
    Color? text1,
    Color? text2,
    Color? text3,
    Color? text4,
    Color? decor,
    Color? decorSoft,
    Color? pink,
    Color? pink2,
    Color? pink3,
    Color? pinkSoft,
    Color? gold,
    Color? gold2,
    Color? gold3,
    Color? goldSoft,
    Color? violet,
    Color? violet2,
    Color? violet3,
    Color? green,
    Color? green2,
    Color? green3,
    Color? red,
    Color? red2,
    Color? blue,
    Color? blue2,
    Color? orange,
    Color? orange2,
    Color? cyan,
    Color? cyan2,
    Color? shDark,
    Color? shDarker,
    Color? shDarkest,
    Color? shLight,
    Color? shLighter,
    Color? shLighter2,
    Color? shDeep,
    Color? shDeep2,
    Color? btnInk,
    Color? btnInk2,
    Color? btnHi,
    Color? btnHi2,
    Color? ripple,
    Color? rippleSoft,
    Color? divider,
    Color? dividerStrong,
    Color? dividerSoft,
    Color? scrim,
    Color? scrimSoft,
    LinearGradient? face,
    LinearGradient? faceHi,
    LinearGradient? faceLo,
    LinearGradient? faceV,
    LinearGradient? faceH,
    LinearGradient? faceAngled,
    LinearGradient? gradBrand,
    LinearGradient? gradBrandH,
    LinearGradient? gradBrandV,
    LinearGradient? gradText,
    LinearGradient? gradTextH,
    LinearGradient? gradGold,
    LinearGradient? gradGoldSoft,
    LinearGradient? gradGreen,
    LinearGradient? gradViolet,
    LinearGradient? gradRed,
    LinearGradient? gradBlue,
    LinearGradient? gradCyan,
    LinearGradient? gradSunset,
    LinearGradient? gradOcean,
    LinearGradient? btnFace,
    LinearGradient? btnFaceV,
    LinearGradient? btnFacePressed,
    LinearGradient? btnFaceGhost,
    Gradient? screenGlow,
    Gradient? screenGlowPink,
    Gradient? screenGlowGold,
    LinearGradient? navFace,
    LinearGradient? navFaceDeep,
    LinearGradient? sidebarFace,
    LinearGradient? sidebarTop,
    LinearGradient? sidebarBottom,
    LinearGradient? cardAccent,
    LinearGradient? cardGold,
    LinearGradient? cardGreen,
    LinearGradient? cardViolet,
    LinearGradient? dividerGrad,
    LinearGradient? shimmer,
    Color? glow1,
    Color? glow2,
    Color? glow3,
    Color? glow4,
    Color? glow5,
    double? noiseOpacity,
  }) =>
      XlPalette(
        hc: hc ?? this.hc,
        isDark: dark ?? this.isDark,
        bg: bg ?? this.bg,
        bgSoft: bgSoft ?? this.bgSoft,
        bgDeep: bgDeep ?? this.bgDeep,
        surface: surface ?? this.surface,
        surfaceHi: surfaceHi ?? this.surfaceHi,
        surfaceLo: surfaceLo ?? this.surfaceLo,
        surfaceAlt: surfaceAlt ?? this.surfaceAlt,
        screen: screen ?? this.screen,
        screenSoft: screenSoft ?? this.screenSoft,
        edge: edge ?? this.edge,
        edgeStrong: edgeStrong ?? this.edgeStrong,
        edgeSoft: edgeSoft ?? this.edgeSoft,
        text1: text1 ?? this.text1,
        text2: text2 ?? this.text2,
        text3: text3 ?? this.text3,
        text4: text4 ?? this.text4,
        decor: decor ?? this.decor,
        decorSoft: decorSoft ?? this.decorSoft,
        pink: pink ?? this.pink,
        pink2: pink2 ?? this.pink2,
        pink3: pink3 ?? this.pink3,
        pinkSoft: pinkSoft ?? this.pinkSoft,
        gold: gold ?? this.gold,
        gold2: gold2 ?? this.gold2,
        gold3: gold3 ?? this.gold3,
        goldSoft: goldSoft ?? this.goldSoft,
        violet: violet ?? this.violet,
        violet2: violet2 ?? this.violet2,
        violet3: violet3 ?? this.violet3,
        green: green ?? this.green,
        green2: green2 ?? this.green2,
        green3: green3 ?? this.green3,
        red: red ?? this.red,
        red2: red2 ?? this.red2,
        blue: blue ?? this.blue,
        blue2: blue2 ?? this.blue2,
        orange: orange ?? this.orange,
        orange2: orange2 ?? this.orange2,
        cyan: cyan ?? this.cyan,
        cyan2: cyan2 ?? this.cyan2,
        shDark: shDark ?? this.shDark,
        shDarker: shDarker ?? this.shDarker,
        shDarkest: shDarkest ?? this.shDarkest,
        shLight: shLight ?? this.shLight,
        shLighter: shLighter ?? this.shLighter,
        shLighter2: shLighter2 ?? this.shLighter2,
        shDeep: shDeep ?? this.shDeep,
        shDeep2: shDeep2 ?? this.shDeep2,
        btnInk: btnInk ?? this.btnInk,
        btnInk2: btnInk2 ?? this.btnInk2,
        btnHi: btnHi ?? this.btnHi,
        btnHi2: btnHi2 ?? this.btnHi2,
        ripple: ripple ?? this.ripple,
        rippleSoft: rippleSoft ?? this.rippleSoft,
        divider: divider ?? this.divider,
        dividerStrong: dividerStrong ?? this.dividerStrong,
        dividerSoft: dividerSoft ?? this.dividerSoft,
        scrim: scrim ?? this.scrim,
        scrimSoft: scrimSoft ?? this.scrimSoft,
        face: face ?? this.face,
        faceHi: faceHi ?? this.faceHi,
        faceLo: faceLo ?? this.faceLo,
        faceV: faceV ?? this.faceV,
        faceH: faceH ?? this.faceH,
        faceAngled: faceAngled ?? this.faceAngled,
        gradBrand: gradBrand ?? this.gradBrand,
        gradBrandH: gradBrandH ?? this.gradBrandH,
        gradBrandV: gradBrandV ?? this.gradBrandV,
        gradText: gradText ?? this.gradText,
        gradTextH: gradTextH ?? this.gradTextH,
        gradGold: gradGold ?? this.gradGold,
        gradGoldSoft: gradGoldSoft ?? this.gradGoldSoft,
        gradGreen: gradGreen ?? this.gradGreen,
        gradViolet: gradViolet ?? this.gradViolet,
        gradRed: gradRed ?? this.gradRed,
        gradBlue: gradBlue ?? this.gradBlue,
        gradCyan: gradCyan ?? this.gradCyan,
        gradSunset: gradSunset ?? this.gradSunset,
        gradOcean: gradOcean ?? this.gradOcean,
        btnFace: btnFace ?? this.btnFace,
        btnFaceV: btnFaceV ?? this.btnFaceV,
        btnFacePressed: btnFacePressed ?? this.btnFacePressed,
        btnFaceGhost: btnFaceGhost ?? this.btnFaceGhost,
        screenGlow: screenGlow ?? this.screenGlow,
        screenGlowPink: screenGlowPink ?? this.screenGlowPink,
        screenGlowGold: screenGlowGold ?? this.screenGlowGold,
        navFace: navFace ?? this.navFace,
        navFaceDeep: navFaceDeep ?? this.navFaceDeep,
        sidebarFace: sidebarFace ?? this.sidebarFace,
        sidebarTop: sidebarTop ?? this.sidebarTop,
        sidebarBottom: sidebarBottom ?? this.sidebarBottom,
        cardAccent: cardAccent ?? this.cardAccent,
        cardGold: cardGold ?? this.cardGold,
        cardGreen: cardGreen ?? this.cardGreen,
        cardViolet: cardViolet ?? this.cardViolet,
        dividerGrad: dividerGrad ?? this.dividerGrad,
        shimmer: shimmer ?? this.shimmer,
        glow1: glow1 ?? this.glow1,
        glow2: glow2 ?? this.glow2,
        glow3: glow3 ?? this.glow3,
        glow4: glow4 ?? this.glow4,
        glow5: glow5 ?? this.glow5,
        noiseOpacity: noiseOpacity ?? this.noiseOpacity,
      );

  @override
  XlPalette lerp(ThemeExtension<XlPalette>? other, double t) {
    if (other is! XlPalette) return this;
    final o = other;
    // 以前这里是 `return t < 0.5 ? this : other;` —— 整个调色板在阈值处
    // 直接跳变，深浅色切换没有过渡。逐字段 lerp 才是真正插值。
    return XlPalette(
      hc: t < 0.5 ? hc : o.hc,
      isDark: t < 0.5 ? isDark : o.isDark,
      bg: Color.lerp(bg, o.bg, t)!,
      bgSoft: Color.lerp(bgSoft, o.bgSoft, t)!,
      bgDeep: Color.lerp(bgDeep, o.bgDeep, t)!,
      surface: Color.lerp(surface, o.surface, t)!,
      surfaceHi: Color.lerp(surfaceHi, o.surfaceHi, t)!,
      surfaceLo: Color.lerp(surfaceLo, o.surfaceLo, t)!,
      surfaceAlt: Color.lerp(surfaceAlt, o.surfaceAlt, t)!,
      screen: Color.lerp(screen, o.screen, t)!,
      screenSoft: Color.lerp(screenSoft, o.screenSoft, t)!,
      edge: Color.lerp(edge, o.edge, t)!,
      edgeStrong: Color.lerp(edgeStrong, o.edgeStrong, t)!,
      edgeSoft: Color.lerp(edgeSoft, o.edgeSoft, t)!,
      text1: Color.lerp(text1, o.text1, t)!,
      text2: Color.lerp(text2, o.text2, t)!,
      text3: Color.lerp(text3, o.text3, t)!,
      text4: Color.lerp(text4, o.text4, t)!,
      decor: Color.lerp(decor, o.decor, t)!,
      decorSoft: Color.lerp(decorSoft, o.decorSoft, t)!,
      pink: Color.lerp(pink, o.pink, t)!,
      pink2: Color.lerp(pink2, o.pink2, t)!,
      pink3: Color.lerp(pink3, o.pink3, t)!,
      pinkSoft: Color.lerp(pinkSoft, o.pinkSoft, t)!,
      gold: Color.lerp(gold, o.gold, t)!,
      gold2: Color.lerp(gold2, o.gold2, t)!,
      gold3: Color.lerp(gold3, o.gold3, t)!,
      goldSoft: Color.lerp(goldSoft, o.goldSoft, t)!,
      violet: Color.lerp(violet, o.violet, t)!,
      violet2: Color.lerp(violet2, o.violet2, t)!,
      violet3: Color.lerp(violet3, o.violet3, t)!,
      green: Color.lerp(green, o.green, t)!,
      green2: Color.lerp(green2, o.green2, t)!,
      green3: Color.lerp(green3, o.green3, t)!,
      red: Color.lerp(red, o.red, t)!,
      red2: Color.lerp(red2, o.red2, t)!,
      blue: Color.lerp(blue, o.blue, t)!,
      blue2: Color.lerp(blue2, o.blue2, t)!,
      orange: Color.lerp(orange, o.orange, t)!,
      orange2: Color.lerp(orange2, o.orange2, t)!,
      cyan: Color.lerp(cyan, o.cyan, t)!,
      cyan2: Color.lerp(cyan2, o.cyan2, t)!,
      shDark: Color.lerp(shDark, o.shDark, t)!,
      shDarker: Color.lerp(shDarker, o.shDarker, t)!,
      shDarkest: Color.lerp(shDarkest, o.shDarkest, t)!,
      shLight: Color.lerp(shLight, o.shLight, t)!,
      shLighter: Color.lerp(shLighter, o.shLighter, t)!,
      shLighter2: Color.lerp(shLighter2, o.shLighter2, t)!,
      shDeep: Color.lerp(shDeep, o.shDeep, t)!,
      shDeep2: Color.lerp(shDeep2, o.shDeep2, t)!,
      btnInk: Color.lerp(btnInk, o.btnInk, t)!,
      btnInk2: Color.lerp(btnInk2, o.btnInk2, t)!,
      btnHi: Color.lerp(btnHi, o.btnHi, t)!,
      btnHi2: Color.lerp(btnHi2, o.btnHi2, t)!,
      ripple: Color.lerp(ripple, o.ripple, t)!,
      rippleSoft: Color.lerp(rippleSoft, o.rippleSoft, t)!,
      divider: Color.lerp(divider, o.divider, t)!,
      dividerStrong: Color.lerp(dividerStrong, o.dividerStrong, t)!,
      dividerSoft: Color.lerp(dividerSoft, o.dividerSoft, t)!,
      scrim: Color.lerp(scrim, o.scrim, t)!,
      scrimSoft: Color.lerp(scrimSoft, o.scrimSoft, t)!,
      face: LinearGradient.lerp(face, o.face, t)!,
      faceHi: LinearGradient.lerp(faceHi, o.faceHi, t)!,
      faceLo: LinearGradient.lerp(faceLo, o.faceLo, t)!,
      faceV: LinearGradient.lerp(faceV, o.faceV, t)!,
      faceH: LinearGradient.lerp(faceH, o.faceH, t)!,
      faceAngled: LinearGradient.lerp(faceAngled, o.faceAngled, t)!,
      gradBrand: LinearGradient.lerp(gradBrand, o.gradBrand, t)!,
      gradBrandH: LinearGradient.lerp(gradBrandH, o.gradBrandH, t)!,
      gradBrandV: LinearGradient.lerp(gradBrandV, o.gradBrandV, t)!,
      gradText: LinearGradient.lerp(gradText, o.gradText, t)!,
      gradTextH: LinearGradient.lerp(gradTextH, o.gradTextH, t)!,
      gradGold: LinearGradient.lerp(gradGold, o.gradGold, t)!,
      gradGoldSoft: LinearGradient.lerp(gradGoldSoft, o.gradGoldSoft, t)!,
      gradGreen: LinearGradient.lerp(gradGreen, o.gradGreen, t)!,
      gradViolet: LinearGradient.lerp(gradViolet, o.gradViolet, t)!,
      gradRed: LinearGradient.lerp(gradRed, o.gradRed, t)!,
      gradBlue: LinearGradient.lerp(gradBlue, o.gradBlue, t)!,
      gradCyan: LinearGradient.lerp(gradCyan, o.gradCyan, t)!,
      gradSunset: LinearGradient.lerp(gradSunset, o.gradSunset, t)!,
      gradOcean: LinearGradient.lerp(gradOcean, o.gradOcean, t)!,
      btnFace: LinearGradient.lerp(btnFace, o.btnFace, t)!,
      btnFaceV: LinearGradient.lerp(btnFaceV, o.btnFaceV, t)!,
      btnFacePressed: LinearGradient.lerp(btnFacePressed, o.btnFacePressed, t)!,
      btnFaceGhost: LinearGradient.lerp(btnFaceGhost, o.btnFaceGhost, t)!,
      screenGlow: Gradient.lerp(screenGlow, o.screenGlow, t)!,
      screenGlowPink: Gradient.lerp(screenGlowPink, o.screenGlowPink, t)!,
      screenGlowGold: Gradient.lerp(screenGlowGold, o.screenGlowGold, t)!,
      navFace: LinearGradient.lerp(navFace, o.navFace, t)!,
      navFaceDeep: LinearGradient.lerp(navFaceDeep, o.navFaceDeep, t)!,
      sidebarFace: LinearGradient.lerp(sidebarFace, o.sidebarFace, t)!,
      sidebarTop: LinearGradient.lerp(sidebarTop, o.sidebarTop, t)!,
      sidebarBottom: LinearGradient.lerp(sidebarBottom, o.sidebarBottom, t)!,
      cardAccent: LinearGradient.lerp(cardAccent, o.cardAccent, t)!,
      cardGold: LinearGradient.lerp(cardGold, o.cardGold, t)!,
      cardGreen: LinearGradient.lerp(cardGreen, o.cardGreen, t)!,
      cardViolet: LinearGradient.lerp(cardViolet, o.cardViolet, t)!,
      dividerGrad: LinearGradient.lerp(dividerGrad, o.dividerGrad, t)!,
      shimmer: LinearGradient.lerp(shimmer, o.shimmer, t)!,
      glow1: Color.lerp(glow1, o.glow1, t)!,
      glow2: Color.lerp(glow2, o.glow2, t)!,
      glow3: Color.lerp(glow3, o.glow3, t)!,
      glow4: Color.lerp(glow4, o.glow4, t)!,
      glow5: Color.lerp(glow5, o.glow5, t)!,
      // lerpDouble 的返回类型是 double?（两个入参都为 null 时才返回 null）。
      // 这里两侧都是非空的 double 字段，故加 `!` 收窄类型；
      // 少了它整个前端在 Windows/Linux/macOS 上都编译不过（GC2F972A8）。
      noiseOpacity: lerpDouble(noiseOpacity, o.noiseOpacity, t)!,
    );
  }
}

class AppTheme {
  /// 系统的「提高对比度」开关。
  ///
  /// 直接读 platformDispatcher，而不是要求调用方提供 BuildContext：
  /// ThemeData 是在 MaterialApp 之上构造的，那里还没有 MediaQuery 可读。
  /// 系统层面的「提高对比度」（Flutter 只在 iOS / macOS / Android 上报，
  /// Windows 与 Linux 恒为 false —— 所以设置页另有应用内三档开关）。
  static bool get systemHighContrast =>
      WidgetsBinding.instance.platformDispatcher.accessibilityFeatures
          .highContrast;

  /// 系统开关 + 设置页档位共同决定是否走高对比配色。
  static bool get useHighContrast =>
      XlThemeController.instance.resolveHighContrast(systemHighContrast);

  static ThemeData get darkTheme =>
      _build(XlPalette.resolve(true, hc: useHighContrast));
  static ThemeData get lightTheme =>
      _build(XlPalette.resolve(false, hc: useHighContrast));

  static ThemeData _build(XlPalette p) {
    final brightness = p.isDark ? Brightness.dark : Brightness.light;
    // Detect platform for Apple text style sizing
    final isMacOS = Platform.isMacOS || Platform.isIOS;
    // Build Apple-aligned TextTheme with font fallback chain (§4)
    final appleTextTheme = XlAppleTextTheme.build(
      text1: p.text1,
      text2: p.text2,
      text3: p.text3,
      text4: p.text4,
      isMacOS: isMacOS,
    );
    return ThemeData(
      useMaterial3: true, brightness: brightness,
      scaffoldBackgroundColor: p.bg, canvasColor: p.bg,
      dividerColor: p.divider, splashColor: Colors.transparent,
      highlightColor: Colors.transparent,
      hoverColor: p.pink.withOpacity(XlOpacity.ghost),
      focusColor: p.pink.withOpacity(XlOpacity.faint),
      disabledColor: p.decorSoft,
      colorScheme: ColorScheme.fromSeed(
        seedColor: p.pink,
        brightness: brightness,
        primary: p.pink,
        secondary: p.gold,
        surface: p.surface,
        error: p.red,
        onPrimary: p.btnInk,
      ),
      extensions: [p],
      // Merge Apple text theme as base, then override display slots with
      // brand-specific weights (w800) that Apple HIG doesn't define.
      textTheme: appleTextTheme.merge(TextTheme(
        displayLarge: XlTextStyles.build(
          size: isMacOS ? 26 : 48, weight: FontWeight.w800,
          color: p.text1, height: XlLineHeight.dense,
          // 不再写死 tighter：48/36/32pt 按 HIG tracking 表应是 **+0.35/
          // +0.37/+0.41**，原来的 −1.2/−0.8 符号相反，大标题挤在一起。
          // 交给 XlTextStyles.build 内部的 trackingFor(size) 取值。
        ),
        displayMedium: XlTextStyles.build(
          size: isMacOS ? 22 : 36,
          weight: FontWeight.w800,
          color: p.text1,
          height: 1.1,
        ),
        displaySmall: XlTextStyles.build(
          size: isMacOS ? 20 : 32,
          weight: FontWeight.w800,
          color: p.text1,
        ),
      )),
      scrollbarTheme: ScrollbarThemeData(
        thumbColor:
            WidgetStatePropertyAll(p.decor.withOpacity(XlOpacity.light)),
        trackColor: const WidgetStatePropertyAll(Colors.transparent),
        radius: const Radius.circular(XlRadius.pill),
        thickness: const WidgetStatePropertyAll(6),
      ),
    );
  }

  static BoxDecoration neuUltra(BuildContext c, {double r = XlRadius.xxxl}) {
    final p = XlPalette.of(c);
    return BoxDecoration(
        gradient: p.face,
        borderRadius: BorderRadius.circular(r),
        border: Border.all(color: p.edge, width: 1),
        boxShadow: p.raisedUltra);
  }

  static BoxDecoration neuXxxl(BuildContext c, {double r = XlRadius.xxxl}) {
    final p = XlPalette.of(c);
    return BoxDecoration(
        gradient: p.face,
        borderRadius: BorderRadius.circular(r),
        border: Border.all(color: p.edge, width: 1),
        boxShadow: p.raisedXxxl);
  }

  static BoxDecoration neuXxl(BuildContext c, {double r = XlRadius.xxl}) {
    final p = XlPalette.of(c);
    return BoxDecoration(
        gradient: p.face,
        borderRadius: BorderRadius.circular(r),
        border: Border.all(color: p.edge, width: 1),
        boxShadow: p.raisedXxl);
  }

  static BoxDecoration neuXl(BuildContext c, {double r = XlRadius.xl}) {
    final p = XlPalette.of(c);
    return BoxDecoration(
        gradient: p.face,
        borderRadius: BorderRadius.circular(r),
        border: Border.all(color: p.edge, width: 1),
        boxShadow: p.raisedXl);
  }

  static BoxDecoration neuLg(BuildContext c, {double r = XlRadius.xxl}) {
    final p = XlPalette.of(c);
    return BoxDecoration(
        gradient: p.face,
        borderRadius: BorderRadius.circular(r),
        border: Border.all(color: p.edge, width: 1),
        boxShadow: p.raised);
  }

  static BoxDecoration neu(BuildContext c, {double r = XlRadius.lg}) {
    final p = XlPalette.of(c);
    return BoxDecoration(
        gradient: p.face,
        borderRadius: BorderRadius.circular(r),
        border: Border.all(color: p.edge, width: 1),
        boxShadow: p.raisedSm);
  }

  static BoxDecoration neuSm(BuildContext c, {double r = XlRadius.md}) {
    final p = XlPalette.of(c);
    return BoxDecoration(
        gradient: p.face,
        borderRadius: BorderRadius.circular(r),
        border: Border.all(color: p.edge, width: 1),
        boxShadow: p.raisedXs);
  }

  static BoxDecoration neuXs(BuildContext c, {double r = XlRadius.sm}) {
    final p = XlPalette.of(c);
    return BoxDecoration(
        gradient: p.face,
        borderRadius: BorderRadius.circular(r),
        border: Border.all(color: p.edge, width: 1),
        boxShadow: p.raisedXs);
  }

  static BoxDecoration neuXxs(BuildContext c, {double r = XlRadius.xs}) {
    final p = XlPalette.of(c);
    return BoxDecoration(
        gradient: p.faceHi,
        borderRadius: BorderRadius.circular(r),
        border: Border.all(color: p.edge, width: 1),
        boxShadow: p.raisedXxs);
  }

  static BoxDecoration neuHair(BuildContext c, {double r = XlRadius.micro}) {
    final p = XlPalette.of(c);
    return BoxDecoration(
        gradient: p.faceHi,
        borderRadius: BorderRadius.circular(r),
        border: Border.all(color: p.edgeSoft, width: 1),
        boxShadow: p.raisedHair);
  }

  static BoxDecoration sunkenHair(BuildContext c, {double r = XlRadius.micro}) {
    final p = XlPalette.of(c);
    return BoxDecoration(
        color: p.surfaceHi,
        borderRadius: BorderRadius.circular(r),
        border: Border.all(
            color: p.shDark.withOpacity(p.isDark ? 0.15 : 0.06), width: 1),
        boxShadow: p.sunkenHair);
  }

  static BoxDecoration sunkenXs(BuildContext c, {double r = XlRadius.sm}) {
    final p = XlPalette.of(c);
    return BoxDecoration(
        color: p.surface,
        borderRadius: BorderRadius.circular(r),
        border: Border.all(
            color: p.shDark.withOpacity(p.isDark ? 0.22 : 0.10), width: 1),
        boxShadow: p.sunkenXs);
  }

  static BoxDecoration sunkenSm(BuildContext c, {double r = XlRadius.md}) {
    final p = XlPalette.of(c);
    return BoxDecoration(
        color: p.surface,
        borderRadius: BorderRadius.circular(r),
        border: Border.all(
            color: p.shDark.withOpacity(p.isDark ? 0.26 : 0.11), width: 1),
        boxShadow: p.sunkenSm);
  }

  static BoxDecoration sunken(BuildContext c, {double r = XlRadius.md}) {
    final p = XlPalette.of(c);
    return BoxDecoration(
        color: p.surface,
        borderRadius: BorderRadius.circular(r),
        border: Border.all(
            color: p.shDark.withOpacity(p.isDark ? 0.30 : 0.13), width: 1),
        boxShadow: p.sunken);
  }

  static BoxDecoration sunkenLg(BuildContext c, {double r = XlRadius.lg}) {
    final p = XlPalette.of(c);
    return BoxDecoration(
        color: p.surfaceLo,
        borderRadius: BorderRadius.circular(r),
        border: Border.all(
            color: p.shDark.withOpacity(p.isDark ? 0.35 : 0.15), width: 1),
        boxShadow: p.sunkenLg);
  }

  static BoxDecoration sunkenDeep(BuildContext c, {double r = XlRadius.md}) {
    final p = XlPalette.of(c);
    return BoxDecoration(
        color: p.surfaceLo,
        borderRadius: BorderRadius.circular(r),
        border: Border.all(
            color: p.shDark.withOpacity(p.isDark ? 0.38 : 0.17), width: 1),
        boxShadow: p.sunkenDeep);
  }

  static BoxDecoration sunkenUltra(BuildContext c, {double r = XlRadius.md}) {
    final p = XlPalette.of(c);
    return BoxDecoration(
        color: p.screen,
        borderRadius: BorderRadius.circular(r),
        border: Border.all(
            color: p.shDark.withOpacity(p.isDark ? 0.45 : 0.20), width: 1),
        boxShadow: p.sunkenUltra);
  }

  static BoxDecoration screen(BuildContext c, {double r = XlRadius.md}) {
    final p = XlPalette.of(c);
    return BoxDecoration(
        color: p.screen,
        borderRadius: BorderRadius.circular(r),
        border: Border.all(
            color: p.shDark.withOpacity(p.isDark ? 0.40 : 0.18), width: 1),
        boxShadow: p.sunkenDeep);
  }

  static BoxDecoration screenSoft(BuildContext c, {double r = XlRadius.md}) {
    final p = XlPalette.of(c);
    return BoxDecoration(
        color: p.screenSoft,
        borderRadius: BorderRadius.circular(r),
        border: Border.all(
            color: p.shDark.withOpacity(p.isDark ? 0.35 : 0.15), width: 1),
        boxShadow: p.sunkenLg);
  }

  static BoxDecoration btn(BuildContext c, {double r = XlRadius.pill}) {
    final p = XlPalette.of(c);
    return BoxDecoration(
        gradient: p.btnFace,
        borderRadius: BorderRadius.circular(r),
        border: Border.all(
            color: Colors.white.withOpacity(p.isDark ? 0.35 : 0.22), width: 1),
        boxShadow: p.raisedXs);
  }

  static BoxDecoration btnLg(BuildContext c, {double r = XlRadius.pill}) {
    final p = XlPalette.of(c);
    return BoxDecoration(
        gradient: p.btnFace,
        borderRadius: BorderRadius.circular(r),
        border: Border.all(
            color: Colors.white.withOpacity(p.isDark ? 0.40 : 0.26), width: 1),
        boxShadow: p.raisedSm);
  }

  static BoxDecoration btnV(BuildContext c, {double r = XlRadius.pill}) {
    final p = XlPalette.of(c);
    return BoxDecoration(
        gradient: p.btnFaceV,
        borderRadius: BorderRadius.circular(r),
        border: Border.all(
            color: Colors.white.withOpacity(p.isDark ? 0.35 : 0.22), width: 1),
        boxShadow: p.raisedXs);
  }

  static BoxDecoration btnPressed(BuildContext c, {double r = XlRadius.pill}) {
    final p = XlPalette.of(c);
    return BoxDecoration(
        gradient: p.btnFacePressed,
        borderRadius: BorderRadius.circular(r),
        border: Border.all(
            color: Colors.white.withOpacity(p.isDark ? 0.18 : 0.10), width: 1),
        boxShadow: p.sunkenSm);
  }

  static BoxDecoration ghost(BuildContext c, {double r = XlRadius.pill}) {
    final p = XlPalette.of(c);
    return BoxDecoration(
        gradient: p.face,
        borderRadius: BorderRadius.circular(r),
        border: Border.all(color: p.edge, width: 1),
        boxShadow: p.raisedXs);
  }

  static BoxDecoration ghostPressed(BuildContext c,
      {double r = XlRadius.pill}) {
    final p = XlPalette.of(c);
    return BoxDecoration(
        color: p.surfaceLo,
        borderRadius: BorderRadius.circular(r),
        border: Border.all(
            color: p.shDark.withOpacity(p.isDark ? 0.30 : 0.13), width: 1),
        boxShadow: p.sunkenSm);
  }

  static BoxDecoration glass(BuildContext c, {double r = XlRadius.lg}) {
    final p = XlPalette.of(c);
    return BoxDecoration(
        color: p.surface.withOpacity(p.isDark ? 0.85 : 0.72),
        borderRadius: BorderRadius.circular(r),
        border: Border.all(color: p.edge, width: 1),
        boxShadow: p.raised);
  }

  static BoxDecoration glassDeep(BuildContext c, {double r = XlRadius.lg}) {
    final p = XlPalette.of(c);
    return BoxDecoration(
        color: p.surface.withOpacity(p.isDark ? 0.92 : 0.85),
        borderRadius: BorderRadius.circular(r),
        border: Border.all(color: p.edge, width: 1),
        boxShadow: p.raisedSm);
  }

  static BoxDecoration scrim(BuildContext c, {double r = XlRadius.lg}) {
    final p = XlPalette.of(c);
    return BoxDecoration(
        color: p.scrim, borderRadius: BorderRadius.circular(r));
  }

  static BoxDecoration accent(BuildContext c, {double r = XlRadius.lg}) {
    final p = XlPalette.of(c);
    return BoxDecoration(
        gradient: p.face,
        borderRadius: BorderRadius.circular(r),
        border: Border.all(color: p.pink.withOpacity(0.35), width: 1.4),
        boxShadow: [
          ...p.raised,
          BoxShadow(
              color: p.pink.withOpacity(p.isDark ? 0.28 : 0.18),
              blurRadius: 26,
              spreadRadius: -6)
        ]);
  }

  static BoxDecoration accentSoft(BuildContext c, {double r = XlRadius.lg}) {
    final p = XlPalette.of(c);
    return BoxDecoration(
        gradient: p.face,
        borderRadius: BorderRadius.circular(r),
        border: Border.all(color: p.pink.withOpacity(0.22), width: 1.2),
        boxShadow: [
          ...p.raisedSm,
          BoxShadow(
              color: p.pink.withOpacity(p.isDark ? 0.18 : 0.12),
              blurRadius: 20,
              spreadRadius: -5)
        ]);
  }

  static BoxDecoration gold(BuildContext c, {double r = XlRadius.lg}) {
    final p = XlPalette.of(c);
    return BoxDecoration(
        gradient: p.face,
        borderRadius: BorderRadius.circular(r),
        border: Border.all(color: p.gold.withOpacity(0.4), width: 1.4),
        boxShadow: [
          ...p.raised,
          BoxShadow(
              color: p.gold.withOpacity(p.isDark ? 0.30 : 0.20),
              blurRadius: 26,
              spreadRadius: -6)
        ]);
  }

  static BoxDecoration green(BuildContext c, {double r = XlRadius.lg}) {
    final p = XlPalette.of(c);
    return BoxDecoration(
        gradient: p.face,
        borderRadius: BorderRadius.circular(r),
        border: Border.all(color: p.green.withOpacity(0.4), width: 1.4),
        boxShadow: [
          ...p.raised,
          BoxShadow(
              color: p.green.withOpacity(p.isDark ? 0.30 : 0.20),
              blurRadius: 26,
              spreadRadius: -6)
        ]);
  }

  static BoxDecoration violet(BuildContext c, {double r = XlRadius.lg}) {
    final p = XlPalette.of(c);
    return BoxDecoration(
        gradient: p.face,
        borderRadius: BorderRadius.circular(r),
        border: Border.all(color: p.violet.withOpacity(0.4), width: 1.4),
        boxShadow: [
          ...p.raised,
          BoxShadow(
              color: p.violet.withOpacity(p.isDark ? 0.30 : 0.20),
              blurRadius: 26,
              spreadRadius: -6)
        ]);
  }

  static BoxDecoration red(BuildContext c, {double r = XlRadius.lg}) {
    final p = XlPalette.of(c);
    return BoxDecoration(
        gradient: p.face,
        borderRadius: BorderRadius.circular(r),
        border: Border.all(color: p.red.withOpacity(0.4), width: 1.4),
        boxShadow: [
          ...p.raised,
          BoxShadow(
              color: p.red.withOpacity(p.isDark ? 0.30 : 0.20),
              blurRadius: 26,
              spreadRadius: -6)
        ]);
  }

  static BoxDecoration brand(BuildContext c, {double r = XlRadius.lg}) {
    final p = XlPalette.of(c);
    return BoxDecoration(
        gradient: p.gradBrand,
        borderRadius: BorderRadius.circular(r),
        border: Border.all(
            color: Colors.white.withOpacity(p.isDark ? 0.35 : 0.5), width: 1),
        boxShadow: p.raisedSm);
  }

  static BoxDecoration brandV(BuildContext c, {double r = XlRadius.lg}) {
    final p = XlPalette.of(c);
    return BoxDecoration(
        gradient: p.gradBrandV,
        borderRadius: BorderRadius.circular(r),
        border: Border.all(
            color: Colors.white.withOpacity(p.isDark ? 0.35 : 0.5), width: 1),
        boxShadow: p.raisedSm);
  }

  static BoxDecoration goldFill(BuildContext c, {double r = XlRadius.lg}) {
    final p = XlPalette.of(c);
    return BoxDecoration(
        gradient: p.gradGold,
        borderRadius: BorderRadius.circular(r),
        border: Border.all(
            color: Colors.white.withOpacity(p.isDark ? 0.30 : 0.45), width: 1),
        boxShadow: p.raisedSm);
  }

  static BoxDecoration greenFill(BuildContext c, {double r = XlRadius.lg}) {
    final p = XlPalette.of(c);
    return BoxDecoration(
        gradient: p.gradGreen,
        borderRadius: BorderRadius.circular(r),
        border: Border.all(
            color: Colors.white.withOpacity(p.isDark ? 0.30 : 0.45), width: 1),
        boxShadow: p.raisedSm);
  }

  static BoxDecoration glowDot(Color color, {double size = 8}) =>
      BoxDecoration(color: color, shape: BoxShape.circle, boxShadow: [
        BoxShadow(
            color: color.withOpacity(0.6),
            blurRadius: size * 1.5,
            spreadRadius: -1)
      ]);
  static BoxDecoration glowDotLg(Color color, {double size = 10}) =>
      BoxDecoration(color: color, shape: BoxShape.circle, boxShadow: [
        BoxShadow(
            color: color.withOpacity(0.7),
            blurRadius: size * 2,
            spreadRadius: -1)
      ]);
  static BoxDecoration brandOrb(BuildContext c, {double size = 44}) {
    final p = XlPalette.of(c);
    return BoxDecoration(
        gradient: p.gradBrand,
        shape: BoxShape.circle,
        border: Border.all(
            color: Colors.white.withOpacity(p.isDark ? 0.35 : 0.5), width: 2),
        boxShadow: [
          ...p.raisedSm,
          BoxShadow(
              color: p.pink.withOpacity(0.4), blurRadius: 22, spreadRadius: -4)
        ]);
  }

  static BoxDecoration brandOrbLg(BuildContext c, {double size = 60}) {
    final p = XlPalette.of(c);
    return BoxDecoration(
        gradient: p.gradBrand,
        shape: BoxShape.circle,
        border: Border.all(
            color: Colors.white.withOpacity(p.isDark ? 0.40 : 0.55), width: 3),
        boxShadow: [
          ...p.raised,
          BoxShadow(
              color: p.pink.withOpacity(0.5), blurRadius: 30, spreadRadius: -6)
        ]);
  }

  static BoxDecoration orb(BuildContext c, {double size = 44, Color? color}) {
    final p = XlPalette.of(c);
    final cc = color ?? p.pink;
    return BoxDecoration(
        gradient: RadialGradient(colors: [
          cc.withOpacity(0.9),
          cc.withOpacity(0.6),
          cc.withOpacity(0.2)
        ]),
        shape: BoxShape.circle,
        border: Border.all(
            color: Colors.white.withOpacity(p.isDark ? 0.20 : 0.40), width: 1),
        boxShadow: [
          ...p.raisedSm,
          BoxShadow(
              color: cc.withOpacity(0.35), blurRadius: 24, spreadRadius: -4)
        ]);
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

  static Widget _blob(Color c, double size) => IgnorePointer(
      child: Container(
          width: size,
          height: size,
          decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: RadialGradient(colors: [c, c.withOpacity(0)]))));
  static Widget divider(BuildContext c, {double height = 1, double inset = 0}) {
    final p = XlPalette.of(c);
    return Padding(
        padding: EdgeInsets.symmetric(horizontal: inset),
        child: Container(
            height: height,
            decoration: BoxDecoration(
                gradient: p.dividerGrad,
                borderRadius: BorderRadius.circular(height))));
  }

  static Widget chip(BuildContext c, String text,
      {Color? color, IconData? icon}) {
    final p = XlPalette.of(c);
    final cc = color ?? p.pink;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: cc.withOpacity(p.isDark ? 0.14 : 0.10),
        borderRadius: BorderRadius.circular(XlRadius.pill),
        border: Border.all(color: cc.withOpacity(0.28), width: 1),
      ),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        if (icon != null) ...[
          Icon(icon, size: 12, color: cc),
          const SizedBox(width: 6)
        ],
        Text(text,
            style: TextStyle(
                fontSize: XlFont.label,
                fontWeight: FontWeight.w700,
                color: cc,
                letterSpacing: XlLetterSpacing.wider)),
      ]),
    );
  }

  static Widget badge(BuildContext c, String text, {Color? color}) {
    final p = XlPalette.of(c);
    final cc = color ?? p.pink;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
          gradient: LinearGradient(colors: [cc, cc.withOpacity(0.85)]),
          borderRadius: BorderRadius.circular(XlRadius.pill),
          boxShadow: [
            BoxShadow(
                color: cc.withOpacity(0.35), blurRadius: 8, spreadRadius: -2)
          ]),
      child: Text(text,
          style: TextStyle(
              fontSize: XlFont.labelSm,
              fontWeight: FontWeight.w800,
              color: p.btnInk,
              letterSpacing: XlLetterSpacing.wider)),
    );
  }

  static Widget statusDot(Color color, {double size = 8, bool glow = true}) =>
      Container(
          width: size,
          height: size,
          decoration: BoxDecoration(
              color: color,
              shape: BoxShape.circle,
              boxShadow: glow
                  ? [
                      BoxShadow(
                          color: color.withOpacity(0.6),
                          blurRadius: size * 1.6,
                          spreadRadius: -1)
                    ]
                  : null));

  static BoxDecoration pill(BuildContext c,
      {Color? color, double r = XlRadius.pill}) {
    final p = XlPalette.of(c);
    final cc = color ?? p.pink;
    return BoxDecoration(
      color: cc.withOpacity(p.isDark ? 0.16 : 0.12),
      borderRadius: BorderRadius.circular(r),
      border: Border.all(color: cc.withOpacity(0.32), width: 1),
    );
  }

  static BoxDecoration cardHeader(BuildContext c, {double r = XlRadius.lg}) {
    final p = XlPalette.of(c);
    return BoxDecoration(
      gradient: p.faceHi,
      borderRadius: BorderRadius.only(
        topLeft: Radius.circular(r),
        topRight: Radius.circular(r),
      ),
      border: Border(bottom: BorderSide(color: p.edge, width: 1)),
    );
  }

  static Widget dividerSunken(BuildContext c,
      {double height = 2, double inset = 0}) {
    final p = XlPalette.of(c);
    return Padding(
      padding: EdgeInsets.symmetric(horizontal: inset),
      child: Container(
        height: height,
        decoration: BoxDecoration(
          color: p.surfaceHi,
          borderRadius: BorderRadius.circular(height),
          boxShadow: [
            BoxShadow(
                color: p.shDark.withOpacity(p.isDark ? 0.25 : 0.10),
                offset: const Offset(0, 1),
                blurRadius: 0),
            BoxShadow(
                color: p.shLight, offset: const Offset(0, -1), blurRadius: 0),
          ],
        ),
      ),
    );
  }
}

extension XlContext on BuildContext {
  XlPalette get xl => XlPalette.of(this);
  bool get isDark => xl.isDark;
  bool get isLight => !xl.isDark;
  bool get isMobile => MediaQuery.of(this).size.width < XlBreakpoint.mobile;
  bool get isTablet => MediaQuery.of(this).size.width < XlBreakpoint.desktopSm;
  bool get isDesktop =>
      MediaQuery.of(this).size.width >= XlBreakpoint.desktopSm;
  double get screenW => MediaQuery.of(this).size.width;
  double get screenH => MediaQuery.of(this).size.height;
  EdgeInsets get viewInsets => MediaQuery.of(this).viewInsets;
  EdgeInsets get viewPadding => MediaQuery.of(this).viewPadding;
}

extension XlTextStyle on TextStyle {
  /// HIG 动态光学尺寸：按当前字号在 Inter / InterDisplay 之间选族。
  ///
  /// 走 XlTextStyles.build() 的样式已经自动处理；但页面里大量
  /// `TextStyle(fontSize: 40)` 这种现场硬写的样式只会从主题继承
  /// Text 光学族，大标题就会偏松。这几处用本 getter 显式纠正。
  TextStyle get optical =>
      copyWith(fontFamily: XlFontFamily.forSize(fontSize ?? 17));
  TextStyle get tabular =>
      copyWith(fontFeatures: const [FontFeature.tabularFigures()]);
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
  Widget padH(double v) =>
      Padding(padding: EdgeInsets.symmetric(horizontal: v), child: this);
  Widget padV(double v) =>
      Padding(padding: EdgeInsets.symmetric(vertical: v), child: this);
  Widget pad(EdgeInsets e) => Padding(padding: e, child: this);
  Widget opacity(double o) => Opacity(opacity: o, child: this);
  Widget get visible => Visibility(visible: true, child: this);
  Widget get hidden => Visibility(visible: false, child: this);
}
