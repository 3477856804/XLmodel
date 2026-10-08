import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart';

class AppLocalizations {
  final Locale locale;
  AppLocalizations(this.locale);

  static const List<Locale> supportedLocales = [
    Locale('zh'),
    Locale('en'),
  ];

  static const LocalizationsDelegate<AppLocalizations> delegate =
      _AppLocalizationsDelegate();

  static AppLocalizations of(BuildContext context) {
    return Localizations.of<AppLocalizations>(context, AppLocalizations) ??
        AppLocalizations(const Locale('zh'));
  }

  bool get isZh => locale.languageCode != 'en';

  static const Map<String, Map<String, String>> _tables = {
    'zh': _zh,
    'en': _en,
  };

  String _t(String key) {
    final table = isZh ? _zh : _en;
    return table[key] ?? _zh[key] ?? key;
  }

  String get appTitle => _t('appTitle');
  String get appSubtitle => _t('appSubtitle');

  String get navChat => _t('navChat');
  String get navDashboard => _t('navDashboard');
  String get navTraining => _t('navTraining');
  String get navGrowth => _t('navGrowth');
  String get navSettings => _t('navSettings');
  String get navModelStore => _t('navModelStore');
  String get navPlugins => _t('navPlugins');

  String get subChat => _t('subChat');
  String get subDashboard => _t('subDashboard');
  String get subTraining => _t('subTraining');
  String get subGrowth => _t('subGrowth');
  String get subSettings => _t('subSettings');
  String get subModelStore => _t('subModelStore');
  String get subPlugins => _t('subPlugins');

  String get more => _t('more');
  String get lightTheme => _t('lightTheme');
  String get darkTheme => _t('darkTheme');

  String get searchHint => _t('searchHint');
  String get noMatch => _t('noMatch');
  String get select => _t('select');
  String get run => _t('run');
  String get searchSwitchTheme => _t('searchSwitchTheme');
  String get searchCollapseSidebar => _t('searchCollapseSidebar');
  String get searchThemeDesc => _t('searchThemeDesc');

  String get interfaceSettings => _t('interfaceSettings');
  String get interfaceSettingsSub => _t('interfaceSettingsSub');
  String get themeMode => _t('themeMode');
  String get themeModeSub => _t('themeModeSub');
  String get language => _t('language');
  String get languageSub => _t('languageSub');
  String get followSystem => _t('followSystem');
  String get chinese => _t('chinese');
  String get english => _t('english');
  String get themeSaved => _t('themeSaved');
  String get langSaved => _t('langSaved');

  String get chatInputHint => _t('chatInputHint');
  String get send => _t('send');
  String get delete => _t('delete');
  String get copy => _t('copy');
  String get copied => _t('copied');
  String get quote => _t('quote');
  String get refreshHistory => _t('refreshHistory');
  String get noMoreHistory => _t('noMoreHistory');

  String get save => _t('save');
  String get saveFailed => _t('saveFailed');
  String get retry => _t('retry');
  String get startupError => _t('startupError');
  String get startupErrorDesc => _t('startupErrorDesc');
  String get softError => _t('softError');
  String get loading => _t('loading');

  static const Map<String, String> _zh = {
    'appTitle': '小凌',
    'appSubtitle': 'XIAOLING',
    'navChat': '聊天',
    'navDashboard': '工作台',
    'navTraining': '训练',
    'navGrowth': '成长',
    'navSettings': '设置',
    'navModelStore': '模型商店',
    'navPlugins': '插件管理',
    'subChat': '和小凌说说话',
    'subDashboard': '一眼看全所有状态',
    'subTraining': 'LoRA 微调面板',
    'subGrowth': '她的成长轨迹',
    'subSettings': '一切都可以调',
    'subModelStore': '挑选适合的模型',
    'subPlugins': '扩展能力边界',
    'more': '更多',
    'lightTheme': '浅色主题',
    'darkTheme': '深色主题',
    'searchHint': '搜索页面、功能或操作…',
    'noMatch': '没有匹配项',
    'select': '选择',
    'run': '执行',
    'searchChat': '聊天',
    'searchDashboard': '工作台',
    'searchTraining': '训练',
    'searchGrowth': '成长',
    'searchSettings': '设置',
    'searchModelStore': '模型商店',
    'searchPlugins': '插件管理',
    'searchSwitchTheme': '切换主题',
    'searchCollapseSidebar': '折叠侧边栏',
    'searchChatDesc': '和小凌说话',
    'searchDashboardDesc': '状态总览',
    'searchTrainingDesc': 'LoRA 微调',
    'searchGrowthDesc': '成长轨迹',
    'searchSettingsDesc': '偏好调整',
    'searchModelStoreDesc': '推荐模型',
    'searchPluginsDesc': '扩展功能',
    'searchThemeDesc': '深色 / 浅色',
    'interfaceSettings': '界面设置',
    'interfaceSettingsSub': '主题、语言与启动行为',
    'themeMode': '主题模式',
    'themeModeSub': '深色为默认，浅色更明亮',
    'language': '界面语言',
    'languageSub': '切换后立即生效',
    'followSystem': '跟随系统',
    'chinese': '简体中文',
    'english': 'English',
    'themeSaved': '主题已切换',
    'langSaved': '语言已切换',
    'chatInputHint': '说点什么…',
    'send': '发送',
    'delete': '删除',
    'copy': '复制',
    'copied': '已复制',
    'quote': '引用',
    'refreshHistory': '正在加载更早的消息…',
    'noMoreHistory': '没有更早的消息了',
    'save': '已保存',
    'saveFailed': '保存失败',
    'retry': '重试',
    'startupError': '启动遇到问题',
    'startupErrorDesc': '请尝试重启应用，或检查后端服务是否正常运行。',
    'softError': '这一块渲染出错了：',
    'loading': '加载中…',
  };

  static const Map<String, String> _en = {
    'appTitle': 'XiaoLing',
    'appSubtitle': 'XIAOLING',
    'navChat': 'Chat',
    'navDashboard': 'Dashboard',
    'navTraining': 'Training',
    'navGrowth': 'Growth',
    'navSettings': 'Settings',
    'navModelStore': 'Model Store',
    'navPlugins': 'Plugins',
    'subChat': 'Talk with XiaoLing',
    'subDashboard': 'All status at a glance',
    'subTraining': 'LoRA fine-tuning panel',
    'subGrowth': 'Her growth journey',
    'subSettings': 'Everything is tunable',
    'subModelStore': 'Pick the right model',
    'subPlugins': 'Extend your capabilities',
    'more': 'MORE',
    'lightTheme': 'Light theme',
    'darkTheme': 'Dark theme',
    'searchHint': 'Search pages, features or actions…',
    'noMatch': 'No matches',
    'select': 'Select',
    'run': 'Run',
    'searchChat': 'Chat',
    'searchDashboard': 'Dashboard',
    'searchTraining': 'Training',
    'searchGrowth': 'Growth',
    'searchSettings': 'Settings',
    'searchModelStore': 'Model Store',
    'searchPlugins': 'Plugins',
    'searchSwitchTheme': 'Switch theme',
    'searchCollapseSidebar': 'Collapse sidebar',
    'searchChatDesc': 'Talk to XiaoLing',
    'searchDashboardDesc': 'Status overview',
    'searchTrainingDesc': 'LoRA fine-tuning',
    'searchGrowthDesc': 'Growth journey',
    'searchSettingsDesc': 'Preferences',
    'searchModelStoreDesc': 'Recommended models',
    'searchPluginsDesc': 'Extend features',
    'searchThemeDesc': 'Dark / Light',
    'interfaceSettings': 'Interface',
    'interfaceSettingsSub': 'Theme, language and startup behavior',
    'themeMode': 'Theme mode',
    'themeModeSub': 'Dark by default, light feels brighter',
    'language': 'Language',
    'languageSub': 'Takes effect immediately',
    'followSystem': 'Follow system',
    'chinese': '简体中文',
    'english': 'English',
    'themeSaved': 'Theme switched',
    'langSaved': 'Language switched',
    'chatInputHint': 'Say something…',
    'send': 'Send',
    'delete': 'Delete',
    'copy': 'Copy',
    'copied': 'Copied',
    'quote': 'Quote',
    'refreshHistory': 'Loading earlier messages…',
    'noMoreHistory': 'No earlier messages',
    'save': 'Saved',
    'saveFailed': 'Save failed',
    'retry': 'Retry',
    'startupError': 'Something went wrong at startup',
    'startupErrorDesc': 'Please restart the app or check whether the backend service is running.',
    'softError': 'This block failed to render: ',
    'loading': 'Loading…',
  };
}

class _AppLocalizationsDelegate
    extends LocalizationsDelegate<AppLocalizations> {
  const _AppLocalizationsDelegate();

  @override
  bool isSupported(Locale locale) =>
      AppLocalizations.supportedLocales
          .map((l) => l.languageCode)
          .contains(locale.languageCode);

  @override
  Future<AppLocalizations> load(Locale locale) {
    final code = locale.languageCode == 'en' ? 'en' : 'zh';
    return SynchronousFuture<AppLocalizations>(AppLocalizations(Locale(code)));
  }

  @override
  bool shouldReload(covariant _AppLocalizationsDelegate old) => false;
}
