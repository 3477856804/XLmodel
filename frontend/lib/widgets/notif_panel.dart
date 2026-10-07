import 'package:flutter/material.dart';
import '../rpc/client.dart';
import '../rpc/xiaoling.pb.dart';
import '../rpc/xiaoling_client_ext.dart';
import '../rpc/xiaoling_ext.dart';
import '../theme/theme.dart';

///铃铛面板：任务进度 + 未读提醒队列。
///
/// 此前铃铛按钮 `onTap: () {}` 是空函数，纯装饰。这里补上真实功能：
/// - 上半区：**训练任务进度**（走 `GetTrainingStatus`，含 epoch / loss / 五维）
/// - 下半区：**未读提醒队列**（走 `ListReminders`，已到期未确认 = 未读）
class NotifPanel extends StatefulWidget {
  const NotifPanel({
    super.key,
    required this.onClose,
    required this.onOpenTraining,
  });

  final VoidCallback onClose;
  final VoidCallback onOpenTraining;

  @override
  State<NotifPanel> createState() => _NotifPanelState();
}

class _NotifPanelState extends State<NotifPanel> {
  TrainingStatusReply? _training;
  ReminderList? _reminders;
  bool _loading = true;
  bool _busy = false;
  String? _err;

  int get _unread => _reminders?.unread ?? 0;
  int get _pending => _reminders?.pending ?? 0;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _err = null;
    });
    try {
      final t = await XlClient.stub.safe(() => XlClient.stub.training());
      final r = await XlClient.stub.safe(() => XlClient.stub.fetchReminders());
      if (!mounted) return;
      setState(() {
        _training = t;
        _reminders = r;
      });
    } catch (e) {
      if (mounted) setState(() => _err = '$e');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _complete(ReminderItem item) async {
    setState(() => _busy = true);
    final r = await XlClient.stub.safe(
      () => XlClient.stub.finishReminder(item.dueAt),
    );
    if (!mounted) return;
    setState(() => _busy = false);
    if (r?.ok ?? false) {
      _toast('已完成提醒');
      await _load();
    } else {
      _toast(r?.message.isNotEmpty == true ? r!.message : '操作失败');
    }
  }

  void _toast(String msg) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(msg), duration: XlDuration.fast),
    );
  }

  @override
  Widget build(BuildContext context) {
    final p = XlPalette.of(context);
    return Positioned.fill(
      child: GestureDetector(
        onTap: widget.onClose,
        child: Container(
          color: p.scrim,
          child: Align(
            alignment: Alignment.topRight,
            child: GestureDetector(
              onTap: () {},
              child: Container(
                width: 400,
                constraints: const BoxConstraints(maxHeight: 620),
                margin: const EdgeInsets.only(top: 68, right: 16),
                decoration: AppTheme.neuLg(context, r: XlRadius.xxl),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    _header(p),
                    AppTheme.divider(context),
                    Flexible(child: _body(p)),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _header(XlPalette p) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(18, 16, 14, 14),
      child: Row(
        children: [
          Icon(Icons.notifications_none_rounded, size: 20, color: p.pink),
          const SizedBox(width: 10),
          Text('消息与任务',
              style: TextStyle(
                  fontSize: XlFont.h6,
                  fontWeight: FontWeight.w800,
                  color: p.text1)),
          const SizedBox(width: 8),
          if (_unread > 0)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
              decoration: BoxDecoration(
                color: p.pink,
                borderRadius: BorderRadius.circular(XlRadius.sm),
              ),
              child: Text('$_unread',
                  style: TextStyle(
                      fontSize: XlFont.micro,
                      fontWeight: FontWeight.w800,
                      color: p.btnInk)),
            ),
          const Spacer(),
          _escChip(p),
        ],
      ),
    );
  }

  Widget _escChip(XlPalette p) {
    return GestureDetector(
      onTap: widget.onClose,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
        decoration: BoxDecoration(
          color: p.surfaceLo,
          borderRadius: BorderRadius.circular(XlRadius.xs),
          border: Border.all(color: p.edge, width: 1),
        ),
        child: Text('关闭',
            style: TextStyle(
                fontSize: XlFont.micro,
                color: p.text3,
                fontWeight: FontWeight.w700)),
      ),
    );
  }

  Widget _body(XlPalette p) {
    if (_loading) {
      return const Padding(
        padding: EdgeInsets.all(40),
        child: Center(child: CircularProgressIndicator(strokeWidth: 2)),
      );
    }
    return ListView(
      shrinkWrap: true,
      padding: const EdgeInsets.all(14),
      children: [
        _trainingCard(p),
        const SizedBox(height: 14),
        _reminderCard(p),
        if (_err != null) ...[
          const SizedBox(height: 10),
          Text(_err!,
              style: TextStyle(fontSize: XlFont.captionSm, color: p.red)),
        ],
      ],
    );
  }

  // ---------------- 任务进度 ----------------
  Widget _trainingCard(XlPalette p) {
    final t = _training;
    final total = t?.totalEpochs ?? 0;
    final cur = t?.currentEpoch ?? 0;
    final pct = total > 0 ? (cur / total * 100).clamp(0.0, 100.0) : 0.0;
    final training = t?.isTraining ?? false;

    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: p.surfaceLo,
        borderRadius: BorderRadius.circular(XlRadius.lg),
        border: Border.all(color: p.edgeSoft, width: 1),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(training ? Icons.bolt_rounded : Icons.auto_graph_rounded,
                  size: 17, color: training ? p.gold : p.violet),
              const SizedBox(width: 8),
              Text('任务进度',
                  style: TextStyle(
                      fontSize: XlFont.bodySm,
                      fontWeight: FontWeight.w800,
                      color: p.text1)),
              const Spacer(),
              _pill(
                p,
                training ? '训练中' : '空闲',
                training ? p.gold : p.text3,
                training ? p.goldSoft : p.surfaceHi,
              ),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text('$cur',
                  style: TextStyle(
                      fontSize: XlFont.h3,
                      fontWeight: FontWeight.w800,
                      color: p.text1,
                      height: 1)),
              Text(' / $total 轮',
                  style: TextStyle(fontSize: XlFont.caption, color: p.text3)),
              const Spacer(),
              Text(t?.statusText.isNotEmpty == true ? t!.statusText : '暂无进行中的任务',
                  style: TextStyle(fontSize: XlFont.captionSm, color: p.text3)),
            ],
          ),
          const SizedBox(height: 10),
          _bar(p, pct, training ? p.gold : p.violet),
          if (t != null && t.loss > 0) ...[
            const SizedBox(height: 10),
            Row(
              children: [
                Icon(Icons.trending_down_rounded, size: 14, color: p.green),
                const SizedBox(width: 4),
                Text('Loss ${t.loss.toStringAsFixed(4)}',
                    style: TextStyle(
                        fontSize: XlFont.captionSm,
                        color: p.text2,
                        fontWeight: FontWeight.w600)),
              ],
            ),
          ],
          if (t != null && t.dimensions.isNotEmpty) ...[
            const SizedBox(height: 14),
            ...t.dimensions.map((d) => Padding(
                  padding: const EdgeInsets.only(bottom: 7),
                  child: Row(
                    children: [
                      SizedBox(
                        width: 34,
                        child: Text(d.name,
                            style: TextStyle(
                                fontSize: XlFont.micro,
                                color: p.text3,
                                fontWeight: FontWeight.w700)),
                      ),
                      Expanded(child: _bar(p, d.value.clamp(0, 100), p.violet, slim: true)),
                      const SizedBox(width: 8),
                      SizedBox(
                        width: 30,
                        child: Text('${d.value.toStringAsFixed(0)}',
                            textAlign: TextAlign.right,
                            style: TextStyle(
                                fontSize: XlFont.micro, color: p.text2)),
                      ),
                    ],
                  ),
                )),
          ],
          const SizedBox(height: 6),
          Align(
            alignment: Alignment.centerRight,
            child: GestureDetector(
              onTap: () {
                widget.onClose();
                widget.onOpenTraining();
              },
              child: Padding(
                padding: const EdgeInsets.all(4),
                child: Text('去训练面板 →',
                    style: TextStyle(
                        fontSize: XlFont.captionSm,
                        color: p.pink,
                        fontWeight: FontWeight.w700)),
              ),
            ),
          ),
        ],
      ),
    );
  }

  // ---------------- 提醒队列 ----------------
  Widget _reminderCard(XlPalette p) {
    final list = _reminders;
    final items = list?.items ?? const <ReminderItem>[];
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: p.surfaceLo,
        borderRadius: BorderRadius.circular(XlRadius.lg),
        border: Border.all(color: p.edgeSoft, width: 1),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.notifications_active_outlined, size: 17, color: p.pink),
              const SizedBox(width: 8),
              Text('提醒队列',
                  style: TextStyle(
                      fontSize: XlFont.bodySm,
                      fontWeight: FontWeight.w800,
                      color: p.text1)),
              const Spacer(),
              Text('$_unread 未读 / $_pending 待办',
                  style: TextStyle(fontSize: XlFont.micro, color: p.text3)),
            ],
          ),
          const SizedBox(height: 10),
          if (items.isEmpty)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 18),
              child: Center(
                child: Text('暂时没有提醒',
                    style: TextStyle(fontSize: XlFont.caption, color: p.text3)),
              ),
            )
          else
            ...items.map((r) => _reminderRow(p, r)),
        ],
      ),
    );
  }

  Widget _reminderRow(XlPalette p, ReminderItem r) {
    final left = r.secondsLeft.toInt();
    final overdue = left <= 0;
    final color = overdue ? p.pink : p.text3;
    return Padding(
      padding: const EdgeInsets.only(top: 8),
      child: Row(
        children: [
          Container(
            width: 6,
            height: 6,
            margin: const EdgeInsets.only(right: 10, top: 5),
            decoration: BoxDecoration(
              color: overdue ? p.pink : p.decor,
              shape: BoxShape.circle,
              boxShadow: overdue
                  ? [BoxShadow(color: p.pink.withOpacity(0.6), blurRadius: 6)]
                  : null,
            ),
          ),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(r.text,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(fontSize: XlFont.captionSm, color: p.text1)),
                const SizedBox(height: 2),
                Text(_timeLabel(left),
                    style: TextStyle(fontSize: XlFont.micro, color: color)),
              ],
            ),
          ),
          const SizedBox(width: 8),
          GestureDetector(
            onTap: _busy ? null : () => _complete(r),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
              decoration: BoxDecoration(
                color: p.surfaceHi,
                borderRadius: BorderRadius.circular(XlRadius.xs),
                border: Border.all(color: p.edge, width: 1),
              ),
              child: Text('完成',
                  style: TextStyle(
                      fontSize: XlFont.micro,
                      color: p.text2,
                      fontWeight: FontWeight.w700)),
            ),
          ),
        ],
      ),
    );
  }

  String _timeLabel(int sec) {
    if (sec <= 0) return '已到期';
    if (sec < 60) return '$sec 秒后';
    if (sec < 3600) return '${(sec / 60).floor()} 分钟后';
    if (sec < 86400) return '${(sec / 3600).floor()} 小时后';
    return '${(sec / 86400).floor()} 天后';
  }

  Widget _pill(XlPalette p, String text, Color fg, Color bg) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(XlRadius.sm),
      ),
      child: Text(text,
          style: TextStyle(
              fontSize: XlFont.micro, color: fg, fontWeight: FontWeight.w800)),
    );
  }

  Widget _bar(XlPalette p, double pct, Color color, {bool slim = false}) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(XlRadius.sm),
      child: Container(
        height: slim ? 4 : 7,
        color: p.surfaceHi,
        child: FractionallySizedBox(
          widthFactor: (pct / 100).clamp(0.0, 1.0),
          child: Container(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: [color.withOpacity(0.75), color],
              ),
            ),
          ),
        ),
      ),
    );
  }
}