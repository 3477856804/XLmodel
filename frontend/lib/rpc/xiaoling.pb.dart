//
//  Generated code. Do not modify.
//  source: xiaoling.proto
//
// @dart = 3.3

// ignore_for_file: annotate_overrides, camel_case_types, comment_references
// ignore_for_file: constant_identifier_names, library_prefixes
// ignore_for_file: non_constant_identifier_names, prefer_final_fields
// ignore_for_file: unnecessary_import, unnecessary_this, unused_import

import 'dart:core' as $core;

import 'package:fixnum/fixnum.dart' as $fixnum;
import 'package:protobuf/protobuf.dart' as $pb;

export 'package:protobuf/protobuf.dart' show GeneratedMessageGenericExtensions;

/// ===== 基础消息 =====
class Empty extends $pb.GeneratedMessage {
  factory Empty() => create();
  Empty._() : super();
  factory Empty.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory Empty.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);

  static final $pb.BuilderInfo _i = $pb.BuilderInfo(_omitMessageNames ? '' : 'Empty', package: const $pb.PackageName(_omitMessageNames ? '' : 'xiaoling'), createEmptyInstance: create)
    ..hasRequiredFields = false
  ;

  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  Empty clone() => Empty()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  Empty copyWith(void Function(Empty) updates) => super.copyWith((message) => updates(message as Empty)) as Empty;

  $pb.BuilderInfo get info_ => _i;

  @$core.pragma('dart2js:noInline')
  static Empty create() => Empty._();
  Empty createEmptyInstance() => create();
  static $pb.PbList<Empty> createRepeated() => $pb.PbList<Empty>();
  @$core.pragma('dart2js:noInline')
  static Empty getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<Empty>(create);
  static Empty? _defaultInstance;
}

class ChatRequest extends $pb.GeneratedMessage {
  factory ChatRequest({
    $core.String? text,
  }) {
    final $result = create();
    if (text != null) {
      $result.text = text;
    }
    return $result;
  }
  ChatRequest._() : super();
  factory ChatRequest.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory ChatRequest.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);

  static final $pb.BuilderInfo _i = $pb.BuilderInfo(_omitMessageNames ? '' : 'ChatRequest', package: const $pb.PackageName(_omitMessageNames ? '' : 'xiaoling'), createEmptyInstance: create)
    ..aOS(1, _omitFieldNames ? '' : 'text')
    ..hasRequiredFields = false
  ;

  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  ChatRequest clone() => ChatRequest()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  ChatRequest copyWith(void Function(ChatRequest) updates) => super.copyWith((message) => updates(message as ChatRequest)) as ChatRequest;

  $pb.BuilderInfo get info_ => _i;

  @$core.pragma('dart2js:noInline')
  static ChatRequest create() => ChatRequest._();
  ChatRequest createEmptyInstance() => create();
  static $pb.PbList<ChatRequest> createRepeated() => $pb.PbList<ChatRequest>();
  @$core.pragma('dart2js:noInline')
  static ChatRequest getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<ChatRequest>(create);
  static ChatRequest? _defaultInstance;

  @$pb.TagNumber(1)
  $core.String get text => $_getSZ(0);
  @$pb.TagNumber(1)
  set text($core.String v) { $_setString(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasText() => $_has(0);
  @$pb.TagNumber(1)
  void clearText() => $_clearField(1);
}

class ChatChunk extends $pb.GeneratedMessage {
  factory ChatChunk({
    $core.String? delta,
    $core.bool? done,
    $core.String? error,
  }) {
    final $result = create();
    if (delta != null) {
      $result.delta = delta;
    }
    if (done != null) {
      $result.done = done;
    }
    if (error != null) {
      $result.error = error;
    }
    return $result;
  }
  ChatChunk._() : super();
  factory ChatChunk.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory ChatChunk.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);

  static final $pb.BuilderInfo _i = $pb.BuilderInfo(_omitMessageNames ? '' : 'ChatChunk', package: const $pb.PackageName(_omitMessageNames ? '' : 'xiaoling'), createEmptyInstance: create)
    ..aOS(1, _omitFieldNames ? '' : 'delta')
    ..aOB(2, _omitFieldNames ? '' : 'done')
    ..aOS(3, _omitFieldNames ? '' : 'error')
    ..hasRequiredFields = false
  ;

  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  ChatChunk clone() => ChatChunk()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  ChatChunk copyWith(void Function(ChatChunk) updates) => super.copyWith((message) => updates(message as ChatChunk)) as ChatChunk;

  $pb.BuilderInfo get info_ => _i;

  @$core.pragma('dart2js:noInline')
  static ChatChunk create() => ChatChunk._();
  ChatChunk createEmptyInstance() => create();
  static $pb.PbList<ChatChunk> createRepeated() => $pb.PbList<ChatChunk>();
  @$core.pragma('dart2js:noInline')
  static ChatChunk getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<ChatChunk>(create);
  static ChatChunk? _defaultInstance;

  @$pb.TagNumber(1)
  $core.String get delta => $_getSZ(0);
  @$pb.TagNumber(1)
  set delta($core.String v) { $_setString(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasDelta() => $_has(0);
  @$pb.TagNumber(1)
  void clearDelta() => $_clearField(1);

  @$pb.TagNumber(2)
  $core.bool get done => $_getBF(1);
  @$pb.TagNumber(2)
  set done($core.bool v) { $_setBool(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasDone() => $_has(1);
  @$pb.TagNumber(2)
  void clearDone() => $_clearField(2);

  @$pb.TagNumber(3)
  $core.String get error => $_getSZ(2);
  @$pb.TagNumber(3)
  set error($core.String v) { $_setString(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasError() => $_has(2);
  @$pb.TagNumber(3)
  void clearError() => $_clearField(3);
}

class StatusRequest extends $pb.GeneratedMessage {
  factory StatusRequest() => create();
  StatusRequest._() : super();
  factory StatusRequest.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory StatusRequest.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);

  static final $pb.BuilderInfo _i = $pb.BuilderInfo(_omitMessageNames ? '' : 'StatusRequest', package: const $pb.PackageName(_omitMessageNames ? '' : 'xiaoling'), createEmptyInstance: create)
    ..hasRequiredFields = false
  ;

  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  StatusRequest clone() => StatusRequest()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  StatusRequest copyWith(void Function(StatusRequest) updates) => super.copyWith((message) => updates(message as StatusRequest)) as StatusRequest;

  $pb.BuilderInfo get info_ => _i;

  @$core.pragma('dart2js:noInline')
  static StatusRequest create() => StatusRequest._();
  StatusRequest createEmptyInstance() => create();
  static $pb.PbList<StatusRequest> createRepeated() => $pb.PbList<StatusRequest>();
  @$core.pragma('dart2js:noInline')
  static StatusRequest getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<StatusRequest>(create);
  static StatusRequest? _defaultInstance;
}

class StatusReply extends $pb.GeneratedMessage {
  factory StatusReply({
    $core.bool? ok,
    $core.String? message,
    $core.String? stage,
    $core.String? model,
    $core.String? backend,
    $core.double? progress,
    $core.String? version,
  }) {
    final $result = create();
    if (ok != null) {
      $result.ok = ok;
    }
    if (message != null) {
      $result.message = message;
    }
    if (stage != null) {
      $result.stage = stage;
    }
    if (model != null) {
      $result.model = model;
    }
    if (backend != null) {
      $result.backend = backend;
    }
    if (progress != null) {
      $result.progress = progress;
    }
    if (version != null) {
      $result.version = version;
    }
    return $result;
  }
  StatusReply._() : super();
  factory StatusReply.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory StatusReply.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);

  static final $pb.BuilderInfo _i = $pb.BuilderInfo(_omitMessageNames ? '' : 'StatusReply', package: const $pb.PackageName(_omitMessageNames ? '' : 'xiaoling'), createEmptyInstance: create)
    ..aOB(1, _omitFieldNames ? '' : 'ok')
    ..aOS(2, _omitFieldNames ? '' : 'message')
    ..aOS(3, _omitFieldNames ? '' : 'stage')
    ..aOS(4, _omitFieldNames ? '' : 'model')
    ..aOS(5, _omitFieldNames ? '' : 'backend')
    ..a<$core.double>(6, _omitFieldNames ? '' : 'progress', $pb.PbFieldType.OD)
    ..aOS(7, _omitFieldNames ? '' : 'version')
    ..hasRequiredFields = false
  ;

  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  StatusReply clone() => StatusReply()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  StatusReply copyWith(void Function(StatusReply) updates) => super.copyWith((message) => updates(message as StatusReply)) as StatusReply;

  $pb.BuilderInfo get info_ => _i;

  @$core.pragma('dart2js:noInline')
  static StatusReply create() => StatusReply._();
  StatusReply createEmptyInstance() => create();
  static $pb.PbList<StatusReply> createRepeated() => $pb.PbList<StatusReply>();
  @$core.pragma('dart2js:noInline')
  static StatusReply getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<StatusReply>(create);
  static StatusReply? _defaultInstance;

  @$pb.TagNumber(1)
  $core.bool get ok => $_getBF(0);
  @$pb.TagNumber(1)
  set ok($core.bool v) { $_setBool(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasOk() => $_has(0);
  @$pb.TagNumber(1)
  void clearOk() => $_clearField(1);

  @$pb.TagNumber(2)
  $core.String get message => $_getSZ(1);
  @$pb.TagNumber(2)
  set message($core.String v) { $_setString(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasMessage() => $_has(1);
  @$pb.TagNumber(2)
  void clearMessage() => $_clearField(2);

  @$pb.TagNumber(3)
  $core.String get stage => $_getSZ(2);
  @$pb.TagNumber(3)
  set stage($core.String v) { $_setString(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasStage() => $_has(2);
  @$pb.TagNumber(3)
  void clearStage() => $_clearField(3);

  @$pb.TagNumber(4)
  $core.String get model => $_getSZ(3);
  @$pb.TagNumber(4)
  set model($core.String v) { $_setString(3, v); }
  @$pb.TagNumber(4)
  $core.bool hasModel() => $_has(3);
  @$pb.TagNumber(4)
  void clearModel() => $_clearField(4);

  @$pb.TagNumber(5)
  $core.String get backend => $_getSZ(4);
  @$pb.TagNumber(5)
  set backend($core.String v) { $_setString(4, v); }
  @$pb.TagNumber(5)
  $core.bool hasBackend() => $_has(4);
  @$pb.TagNumber(5)
  void clearBackend() => $_clearField(5);

  @$pb.TagNumber(6)
  $core.double get progress => $_getN(5);
  @$pb.TagNumber(6)
  set progress($core.double v) { $_setDouble(5, v); }
  @$pb.TagNumber(6)
  $core.bool hasProgress() => $_has(5);
  @$pb.TagNumber(6)
  void clearProgress() => $_clearField(6);

  @$pb.TagNumber(7)
  $core.String get version => $_getSZ(6);
  @$pb.TagNumber(7)
  set version($core.String v) { $_setString(6, v); }
  @$pb.TagNumber(7)
  $core.bool hasVersion() => $_has(6);
  @$pb.TagNumber(7)
  void clearVersion() => $_clearField(7);
}

class ListRequest extends $pb.GeneratedMessage {
  factory ListRequest() => create();
  ListRequest._() : super();
  factory ListRequest.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory ListRequest.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);

  static final $pb.BuilderInfo _i = $pb.BuilderInfo(_omitMessageNames ? '' : 'ListRequest', package: const $pb.PackageName(_omitMessageNames ? '' : 'xiaoling'), createEmptyInstance: create)
    ..hasRequiredFields = false
  ;

  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  ListRequest clone() => ListRequest()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  ListRequest copyWith(void Function(ListRequest) updates) => super.copyWith((message) => updates(message as ListRequest)) as ListRequest;

  $pb.BuilderInfo get info_ => _i;

  @$core.pragma('dart2js:noInline')
  static ListRequest create() => ListRequest._();
  ListRequest createEmptyInstance() => create();
  static $pb.PbList<ListRequest> createRepeated() => $pb.PbList<ListRequest>();
  @$core.pragma('dart2js:noInline')
  static ListRequest getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<ListRequest>(create);
  static ListRequest? _defaultInstance;
}

class ModelInfo extends $pb.GeneratedMessage {
  factory ModelInfo({
    $core.String? name,
    $core.String? path,
    $core.double? sizeMb,
  }) {
    final $result = create();
    if (name != null) {
      $result.name = name;
    }
    if (path != null) {
      $result.path = path;
    }
    if (sizeMb != null) {
      $result.sizeMb = sizeMb;
    }
    return $result;
  }
  ModelInfo._() : super();
  factory ModelInfo.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory ModelInfo.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);

  static final $pb.BuilderInfo _i = $pb.BuilderInfo(_omitMessageNames ? '' : 'ModelInfo', package: const $pb.PackageName(_omitMessageNames ? '' : 'xiaoling'), createEmptyInstance: create)
    ..aOS(1, _omitFieldNames ? '' : 'name')
    ..aOS(2, _omitFieldNames ? '' : 'path')
    ..a<$core.double>(3, _omitFieldNames ? '' : 'sizeMb', $pb.PbFieldType.OD)
    ..hasRequiredFields = false
  ;

  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  ModelInfo clone() => ModelInfo()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  ModelInfo copyWith(void Function(ModelInfo) updates) => super.copyWith((message) => updates(message as ModelInfo)) as ModelInfo;

  $pb.BuilderInfo get info_ => _i;

  @$core.pragma('dart2js:noInline')
  static ModelInfo create() => ModelInfo._();
  ModelInfo createEmptyInstance() => create();
  static $pb.PbList<ModelInfo> createRepeated() => $pb.PbList<ModelInfo>();
  @$core.pragma('dart2js:noInline')
  static ModelInfo getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<ModelInfo>(create);
  static ModelInfo? _defaultInstance;

  @$pb.TagNumber(1)
  $core.String get name => $_getSZ(0);
  @$pb.TagNumber(1)
  set name($core.String v) { $_setString(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasName() => $_has(0);
  @$pb.TagNumber(1)
  void clearName() => $_clearField(1);

  @$pb.TagNumber(2)
  $core.String get path => $_getSZ(1);
  @$pb.TagNumber(2)
  set path($core.String v) { $_setString(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasPath() => $_has(1);
  @$pb.TagNumber(2)
  void clearPath() => $_clearField(2);

  @$pb.TagNumber(3)
  $core.double get sizeMb => $_getN(2);
  @$pb.TagNumber(3)
  set sizeMb($core.double v) { $_setDouble(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasSizeMb() => $_has(2);
  @$pb.TagNumber(3)
  void clearSizeMb() => $_clearField(3);
}

class ModelList extends $pb.GeneratedMessage {
  factory ModelList({
    $core.Iterable<ModelInfo>? models,
  }) {
    final $result = create();
    if (models != null) {
      $result.models.addAll(models);
    }
    return $result;
  }
  ModelList._() : super();
  factory ModelList.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory ModelList.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);

  static final $pb.BuilderInfo _i = $pb.BuilderInfo(_omitMessageNames ? '' : 'ModelList', package: const $pb.PackageName(_omitMessageNames ? '' : 'xiaoling'), createEmptyInstance: create)
    ..pc<ModelInfo>(1, _omitFieldNames ? '' : 'models', $pb.PbFieldType.PM, subBuilder: ModelInfo.create)
    ..hasRequiredFields = false
  ;

  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  ModelList clone() => ModelList()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  ModelList copyWith(void Function(ModelList) updates) => super.copyWith((message) => updates(message as ModelList)) as ModelList;

  $pb.BuilderInfo get info_ => _i;

  @$core.pragma('dart2js:noInline')
  static ModelList create() => ModelList._();
  ModelList createEmptyInstance() => create();
  static $pb.PbList<ModelList> createRepeated() => $pb.PbList<ModelList>();
  @$core.pragma('dart2js:noInline')
  static ModelList getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<ModelList>(create);
  static ModelList? _defaultInstance;

  @$pb.TagNumber(1)
  $pb.PbList<ModelInfo> get models => $_getList(0);
}

class SwitchModelRequest extends $pb.GeneratedMessage {
  factory SwitchModelRequest({
    $core.String? path,
  }) {
    final $result = create();
    if (path != null) {
      $result.path = path;
    }
    return $result;
  }
  SwitchModelRequest._() : super();
  factory SwitchModelRequest.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory SwitchModelRequest.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);

  static final $pb.BuilderInfo _i = $pb.BuilderInfo(_omitMessageNames ? '' : 'SwitchModelRequest', package: const $pb.PackageName(_omitMessageNames ? '' : 'xiaoling'), createEmptyInstance: create)
    ..aOS(1, _omitFieldNames ? '' : 'path')
    ..hasRequiredFields = false
  ;

  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  SwitchModelRequest clone() => SwitchModelRequest()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  SwitchModelRequest copyWith(void Function(SwitchModelRequest) updates) => super.copyWith((message) => updates(message as SwitchModelRequest)) as SwitchModelRequest;

  $pb.BuilderInfo get info_ => _i;

  @$core.pragma('dart2js:noInline')
  static SwitchModelRequest create() => SwitchModelRequest._();
  SwitchModelRequest createEmptyInstance() => create();
  static $pb.PbList<SwitchModelRequest> createRepeated() => $pb.PbList<SwitchModelRequest>();
  @$core.pragma('dart2js:noInline')
  static SwitchModelRequest getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<SwitchModelRequest>(create);
  static SwitchModelRequest? _defaultInstance;

  @$pb.TagNumber(1)
  $core.String get path => $_getSZ(0);
  @$pb.TagNumber(1)
  set path($core.String v) { $_setString(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasPath() => $_has(0);
  @$pb.TagNumber(1)
  void clearPath() => $_clearField(1);
}

class CommandRequest extends $pb.GeneratedMessage {
  factory CommandRequest({
    $core.String? command,
  }) {
    final $result = create();
    if (command != null) {
      $result.command = command;
    }
    return $result;
  }
  CommandRequest._() : super();
  factory CommandRequest.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory CommandRequest.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);

  static final $pb.BuilderInfo _i = $pb.BuilderInfo(_omitMessageNames ? '' : 'CommandRequest', package: const $pb.PackageName(_omitMessageNames ? '' : 'xiaoling'), createEmptyInstance: create)
    ..aOS(1, _omitFieldNames ? '' : 'command')
    ..hasRequiredFields = false
  ;

  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  CommandRequest clone() => CommandRequest()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  CommandRequest copyWith(void Function(CommandRequest) updates) => super.copyWith((message) => updates(message as CommandRequest)) as CommandRequest;

  $pb.BuilderInfo get info_ => _i;

  @$core.pragma('dart2js:noInline')
  static CommandRequest create() => CommandRequest._();
  CommandRequest createEmptyInstance() => create();
  static $pb.PbList<CommandRequest> createRepeated() => $pb.PbList<CommandRequest>();
  @$core.pragma('dart2js:noInline')
  static CommandRequest getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<CommandRequest>(create);
  static CommandRequest? _defaultInstance;

  @$pb.TagNumber(1)
  $core.String get command => $_getSZ(0);
  @$pb.TagNumber(1)
  set command($core.String v) { $_setString(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasCommand() => $_has(0);
  @$pb.TagNumber(1)
  void clearCommand() => $_clearField(1);
}

class CommandReply extends $pb.GeneratedMessage {
  factory CommandReply({
    $core.String? output,
  }) {
    final $result = create();
    if (output != null) {
      $result.output = output;
    }
    return $result;
  }
  CommandReply._() : super();
  factory CommandReply.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory CommandReply.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);

  static final $pb.BuilderInfo _i = $pb.BuilderInfo(_omitMessageNames ? '' : 'CommandReply', package: const $pb.PackageName(_omitMessageNames ? '' : 'xiaoling'), createEmptyInstance: create)
    ..aOS(1, _omitFieldNames ? '' : 'output')
    ..hasRequiredFields = false
  ;

  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  CommandReply clone() => CommandReply()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  CommandReply copyWith(void Function(CommandReply) updates) => super.copyWith((message) => updates(message as CommandReply)) as CommandReply;

  $pb.BuilderInfo get info_ => _i;

  @$core.pragma('dart2js:noInline')
  static CommandReply create() => CommandReply._();
  CommandReply createEmptyInstance() => create();
  static $pb.PbList<CommandReply> createRepeated() => $pb.PbList<CommandReply>();
  @$core.pragma('dart2js:noInline')
  static CommandReply getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<CommandReply>(create);
  static CommandReply? _defaultInstance;

  @$pb.TagNumber(1)
  $core.String get output => $_getSZ(0);
  @$pb.TagNumber(1)
  set output($core.String v) { $_setString(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasOutput() => $_has(0);
  @$pb.TagNumber(1)
  void clearOutput() => $_clearField(1);
}

class ActionInfo extends $pb.GeneratedMessage {
  factory ActionInfo({
    $core.String? name,
    $core.String? path,
    $core.bool? dance,
    $core.bool? idle,
  }) {
    final $result = create();
    if (name != null) {
      $result.name = name;
    }
    if (path != null) {
      $result.path = path;
    }
    if (dance != null) {
      $result.dance = dance;
    }
    if (idle != null) {
      $result.idle = idle;
    }
    return $result;
  }
  ActionInfo._() : super();
  factory ActionInfo.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory ActionInfo.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);

  static final $pb.BuilderInfo _i = $pb.BuilderInfo(_omitMessageNames ? '' : 'ActionInfo', package: const $pb.PackageName(_omitMessageNames ? '' : 'xiaoling'), createEmptyInstance: create)
    ..aOS(1, _omitFieldNames ? '' : 'name')
    ..aOS(2, _omitFieldNames ? '' : 'path')
    ..aOB(3, _omitFieldNames ? '' : 'dance')
    ..aOB(4, _omitFieldNames ? '' : 'idle')
    ..hasRequiredFields = false
  ;

  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  ActionInfo clone() => ActionInfo()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  ActionInfo copyWith(void Function(ActionInfo) updates) => super.copyWith((message) => updates(message as ActionInfo)) as ActionInfo;

  $pb.BuilderInfo get info_ => _i;

  @$core.pragma('dart2js:noInline')
  static ActionInfo create() => ActionInfo._();
  ActionInfo createEmptyInstance() => create();
  static $pb.PbList<ActionInfo> createRepeated() => $pb.PbList<ActionInfo>();
  @$core.pragma('dart2js:noInline')
  static ActionInfo getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<ActionInfo>(create);
  static ActionInfo? _defaultInstance;

  @$pb.TagNumber(1)
  $core.String get name => $_getSZ(0);
  @$pb.TagNumber(1)
  set name($core.String v) { $_setString(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasName() => $_has(0);
  @$pb.TagNumber(1)
  void clearName() => $_clearField(1);

  @$pb.TagNumber(2)
  $core.String get path => $_getSZ(1);
  @$pb.TagNumber(2)
  set path($core.String v) { $_setString(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasPath() => $_has(1);
  @$pb.TagNumber(2)
  void clearPath() => $_clearField(2);

  @$pb.TagNumber(3)
  $core.bool get dance => $_getBF(2);
  @$pb.TagNumber(3)
  set dance($core.bool v) { $_setBool(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasDance() => $_has(2);
  @$pb.TagNumber(3)
  void clearDance() => $_clearField(3);

  @$pb.TagNumber(4)
  $core.bool get idle => $_getBF(3);
  @$pb.TagNumber(4)
  set idle($core.bool v) { $_setBool(3, v); }
  @$pb.TagNumber(4)
  $core.bool hasIdle() => $_has(3);
  @$pb.TagNumber(4)
  void clearIdle() => $_clearField(4);
}

class ActionList extends $pb.GeneratedMessage {
  factory ActionList({
    $core.Iterable<ActionInfo>? actions,
  }) {
    final $result = create();
    if (actions != null) {
      $result.actions.addAll(actions);
    }
    return $result;
  }
  ActionList._() : super();
  factory ActionList.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory ActionList.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);

  static final $pb.BuilderInfo _i = $pb.BuilderInfo(_omitMessageNames ? '' : 'ActionList', package: const $pb.PackageName(_omitMessageNames ? '' : 'xiaoling'), createEmptyInstance: create)
    ..pc<ActionInfo>(1, _omitFieldNames ? '' : 'actions', $pb.PbFieldType.PM, subBuilder: ActionInfo.create)
    ..hasRequiredFields = false
  ;

  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  ActionList clone() => ActionList()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  ActionList copyWith(void Function(ActionList) updates) => super.copyWith((message) => updates(message as ActionList)) as ActionList;

  $pb.BuilderInfo get info_ => _i;

  @$core.pragma('dart2js:noInline')
  static ActionList create() => ActionList._();
  ActionList createEmptyInstance() => create();
  static $pb.PbList<ActionList> createRepeated() => $pb.PbList<ActionList>();
  @$core.pragma('dart2js:noInline')
  static ActionList getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<ActionList>(create);
  static ActionList? _defaultInstance;

  @$pb.TagNumber(1)
  $pb.PbList<ActionInfo> get actions => $_getList(0);
}

class PlayActionRequest extends $pb.GeneratedMessage {
  factory PlayActionRequest({
    $core.String? path,
  }) {
    final $result = create();
    if (path != null) {
      $result.path = path;
    }
    return $result;
  }
  PlayActionRequest._() : super();
  factory PlayActionRequest.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory PlayActionRequest.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);

  static final $pb.BuilderInfo _i = $pb.BuilderInfo(_omitMessageNames ? '' : 'PlayActionRequest', package: const $pb.PackageName(_omitMessageNames ? '' : 'xiaoling'), createEmptyInstance: create)
    ..aOS(1, _omitFieldNames ? '' : 'path')
    ..hasRequiredFields = false
  ;

  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  PlayActionRequest clone() => PlayActionRequest()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  PlayActionRequest copyWith(void Function(PlayActionRequest) updates) => super.copyWith((message) => updates(message as PlayActionRequest)) as PlayActionRequest;

  $pb.BuilderInfo get info_ => _i;

  @$core.pragma('dart2js:noInline')
  static PlayActionRequest create() => PlayActionRequest._();
  PlayActionRequest createEmptyInstance() => create();
  static $pb.PbList<PlayActionRequest> createRepeated() => $pb.PbList<PlayActionRequest>();
  @$core.pragma('dart2js:noInline')
  static PlayActionRequest getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<PlayActionRequest>(create);
  static PlayActionRequest? _defaultInstance;

  @$pb.TagNumber(1)
  $core.String get path => $_getSZ(0);
  @$pb.TagNumber(1)
  set path($core.String v) { $_setString(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasPath() => $_has(0);
  @$pb.TagNumber(1)
  void clearPath() => $_clearField(1);
}

class ShutdownRequest extends $pb.GeneratedMessage {
  factory ShutdownRequest() => create();
  ShutdownRequest._() : super();
  factory ShutdownRequest.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory ShutdownRequest.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);

  static final $pb.BuilderInfo _i = $pb.BuilderInfo(_omitMessageNames ? '' : 'ShutdownRequest', package: const $pb.PackageName(_omitMessageNames ? '' : 'xiaoling'), createEmptyInstance: create)
    ..hasRequiredFields = false
  ;

  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  ShutdownRequest clone() => ShutdownRequest()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  ShutdownRequest copyWith(void Function(ShutdownRequest) updates) => super.copyWith((message) => updates(message as ShutdownRequest)) as ShutdownRequest;

  $pb.BuilderInfo get info_ => _i;

  @$core.pragma('dart2js:noInline')
  static ShutdownRequest create() => ShutdownRequest._();
  ShutdownRequest createEmptyInstance() => create();
  static $pb.PbList<ShutdownRequest> createRepeated() => $pb.PbList<ShutdownRequest>();
  @$core.pragma('dart2js:noInline')
  static ShutdownRequest getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<ShutdownRequest>(create);
  static ShutdownRequest? _defaultInstance;
}

/// ===== 成长状态（Flutter 可视化） =====
class GrowthStatusReply extends $pb.GeneratedMessage {
  factory GrowthStatusReply({
    $core.String? stage,
    $core.double? progressPercent,
    $core.int? totalInteractions,
    $core.int? currentGeneration,
    $core.int? totalGenerations,
    $core.String? currentRank,
    $core.String? emotion,
    $core.bool? trainingPaused,
    $core.String? statusText,
  }) {
    final $result = create();
    if (stage != null) {
      $result.stage = stage;
    }
    if (progressPercent != null) {
      $result.progressPercent = progressPercent;
    }
    if (totalInteractions != null) {
      $result.totalInteractions = totalInteractions;
    }
    if (currentGeneration != null) {
      $result.currentGeneration = currentGeneration;
    }
    if (totalGenerations != null) {
      $result.totalGenerations = totalGenerations;
    }
    if (currentRank != null) {
      $result.currentRank = currentRank;
    }
    if (emotion != null) {
      $result.emotion = emotion;
    }
    if (trainingPaused != null) {
      $result.trainingPaused = trainingPaused;
    }
    if (statusText != null) {
      $result.statusText = statusText;
    }
    return $result;
  }
  GrowthStatusReply._() : super();
  factory GrowthStatusReply.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory GrowthStatusReply.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);

  static final $pb.BuilderInfo _i = $pb.BuilderInfo(_omitMessageNames ? '' : 'GrowthStatusReply', package: const $pb.PackageName(_omitMessageNames ? '' : 'xiaoling'), createEmptyInstance: create)
    ..aOS(1, _omitFieldNames ? '' : 'stage')
    ..a<$core.double>(2, _omitFieldNames ? '' : 'progressPercent', $pb.PbFieldType.OD)
    ..a<$core.int>(3, _omitFieldNames ? '' : 'totalInteractions', $pb.PbFieldType.O3)
    ..a<$core.int>(4, _omitFieldNames ? '' : 'currentGeneration', $pb.PbFieldType.O3)
    ..a<$core.int>(5, _omitFieldNames ? '' : 'totalGenerations', $pb.PbFieldType.O3)
    ..aOS(6, _omitFieldNames ? '' : 'currentRank')
    ..aOS(7, _omitFieldNames ? '' : 'emotion')
    ..aOB(8, _omitFieldNames ? '' : 'trainingPaused')
    ..aOS(9, _omitFieldNames ? '' : 'statusText')
    ..hasRequiredFields = false
  ;

  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  GrowthStatusReply clone() => GrowthStatusReply()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  GrowthStatusReply copyWith(void Function(GrowthStatusReply) updates) => super.copyWith((message) => updates(message as GrowthStatusReply)) as GrowthStatusReply;

  $pb.BuilderInfo get info_ => _i;

  @$core.pragma('dart2js:noInline')
  static GrowthStatusReply create() => GrowthStatusReply._();
  GrowthStatusReply createEmptyInstance() => create();
  static $pb.PbList<GrowthStatusReply> createRepeated() => $pb.PbList<GrowthStatusReply>();
  @$core.pragma('dart2js:noInline')
  static GrowthStatusReply getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<GrowthStatusReply>(create);
  static GrowthStatusReply? _defaultInstance;

  @$pb.TagNumber(1)
  $core.String get stage => $_getSZ(0);
  @$pb.TagNumber(1)
  set stage($core.String v) { $_setString(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasStage() => $_has(0);
  @$pb.TagNumber(1)
  void clearStage() => $_clearField(1);

  @$pb.TagNumber(2)
  $core.double get progressPercent => $_getN(1);
  @$pb.TagNumber(2)
  set progressPercent($core.double v) { $_setDouble(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasProgressPercent() => $_has(1);
  @$pb.TagNumber(2)
  void clearProgressPercent() => $_clearField(2);

  @$pb.TagNumber(3)
  $core.int get totalInteractions => $_getIZ(2);
  @$pb.TagNumber(3)
  set totalInteractions($core.int v) { $_setSignedInt32(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasTotalInteractions() => $_has(2);
  @$pb.TagNumber(3)
  void clearTotalInteractions() => $_clearField(3);

  @$pb.TagNumber(4)
  $core.int get currentGeneration => $_getIZ(3);
  @$pb.TagNumber(4)
  set currentGeneration($core.int v) { $_setSignedInt32(3, v); }
  @$pb.TagNumber(4)
  $core.bool hasCurrentGeneration() => $_has(3);
  @$pb.TagNumber(4)
  void clearCurrentGeneration() => $_clearField(4);

  @$pb.TagNumber(5)
  $core.int get totalGenerations => $_getIZ(4);
  @$pb.TagNumber(5)
  set totalGenerations($core.int v) { $_setSignedInt32(4, v); }
  @$pb.TagNumber(5)
  $core.bool hasTotalGenerations() => $_has(4);
  @$pb.TagNumber(5)
  void clearTotalGenerations() => $_clearField(5);

  @$pb.TagNumber(6)
  $core.String get currentRank => $_getSZ(5);
  @$pb.TagNumber(6)
  set currentRank($core.String v) { $_setString(5, v); }
  @$pb.TagNumber(6)
  $core.bool hasCurrentRank() => $_has(5);
  @$pb.TagNumber(6)
  void clearCurrentRank() => $_clearField(6);

  @$pb.TagNumber(7)
  $core.String get emotion => $_getSZ(6);
  @$pb.TagNumber(7)
  set emotion($core.String v) { $_setString(6, v); }
  @$pb.TagNumber(7)
  $core.bool hasEmotion() => $_has(6);
  @$pb.TagNumber(7)
  void clearEmotion() => $_clearField(7);

  @$pb.TagNumber(8)
  $core.bool get trainingPaused => $_getBF(7);
  @$pb.TagNumber(8)
  set trainingPaused($core.bool v) { $_setBool(7, v); }
  @$pb.TagNumber(8)
  $core.bool hasTrainingPaused() => $_has(7);
  @$pb.TagNumber(8)
  void clearTrainingPaused() => $_clearField(8);

  @$pb.TagNumber(9)
  $core.String get statusText => $_getSZ(8);
  @$pb.TagNumber(9)
  set statusText($core.String v) { $_setString(8, v); }
  @$pb.TagNumber(9)
  $core.bool hasStatusText() => $_has(8);
  @$pb.TagNumber(9)
  void clearStatusText() => $_clearField(9);
}

/// ===== 训练状态（Flutter 五维可视化） =====
class TrainingDimension extends $pb.GeneratedMessage {
  factory TrainingDimension({
    $core.String? name,
    $core.double? value,
    $core.String? label,
  }) {
    final $result = create();
    if (name != null) {
      $result.name = name;
    }
    if (value != null) {
      $result.value = value;
    }
    if (label != null) {
      $result.label = label;
    }
    return $result;
  }
  TrainingDimension._() : super();
  factory TrainingDimension.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory TrainingDimension.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);

  static final $pb.BuilderInfo _i = $pb.BuilderInfo(_omitMessageNames ? '' : 'TrainingDimension', package: const $pb.PackageName(_omitMessageNames ? '' : 'xiaoling'), createEmptyInstance: create)
    ..aOS(1, _omitFieldNames ? '' : 'name')
    ..a<$core.double>(2, _omitFieldNames ? '' : 'value', $pb.PbFieldType.OD)
    ..aOS(3, _omitFieldNames ? '' : 'label')
    ..hasRequiredFields = false
  ;

  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  TrainingDimension clone() => TrainingDimension()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  TrainingDimension copyWith(void Function(TrainingDimension) updates) => super.copyWith((message) => updates(message as TrainingDimension)) as TrainingDimension;

  $pb.BuilderInfo get info_ => _i;

  @$core.pragma('dart2js:noInline')
  static TrainingDimension create() => TrainingDimension._();
  TrainingDimension createEmptyInstance() => create();
  static $pb.PbList<TrainingDimension> createRepeated() => $pb.PbList<TrainingDimension>();
  @$core.pragma('dart2js:noInline')
  static TrainingDimension getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<TrainingDimension>(create);
  static TrainingDimension? _defaultInstance;

  @$pb.TagNumber(1)
  $core.String get name => $_getSZ(0);
  @$pb.TagNumber(1)
  set name($core.String v) { $_setString(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasName() => $_has(0);
  @$pb.TagNumber(1)
  void clearName() => $_clearField(1);

  @$pb.TagNumber(2)
  $core.double get value => $_getN(1);
  @$pb.TagNumber(2)
  set value($core.double v) { $_setDouble(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasValue() => $_has(1);
  @$pb.TagNumber(2)
  void clearValue() => $_clearField(2);

  @$pb.TagNumber(3)
  $core.String get label => $_getSZ(2);
  @$pb.TagNumber(3)
  set label($core.String v) { $_setString(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasLabel() => $_has(2);
  @$pb.TagNumber(3)
  void clearLabel() => $_clearField(3);
}

class TrainingStatusReply extends $pb.GeneratedMessage {
  factory TrainingStatusReply({
    $core.bool? isTraining,
    $core.int? currentEpoch,
    $core.int? totalEpochs,
    $core.double? loss,
    $core.Iterable<TrainingDimension>? dimensions,
    $core.String? statusText,
  }) {
    final $result = create();
    if (isTraining != null) {
      $result.isTraining = isTraining;
    }
    if (currentEpoch != null) {
      $result.currentEpoch = currentEpoch;
    }
    if (totalEpochs != null) {
      $result.totalEpochs = totalEpochs;
    }
    if (loss != null) {
      $result.loss = loss;
    }
    if (dimensions != null) {
      $result.dimensions.addAll(dimensions);
    }
    if (statusText != null) {
      $result.statusText = statusText;
    }
    return $result;
  }
  TrainingStatusReply._() : super();
  factory TrainingStatusReply.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory TrainingStatusReply.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);

  static final $pb.BuilderInfo _i = $pb.BuilderInfo(_omitMessageNames ? '' : 'TrainingStatusReply', package: const $pb.PackageName(_omitMessageNames ? '' : 'xiaoling'), createEmptyInstance: create)
    ..aOB(1, _omitFieldNames ? '' : 'isTraining')
    ..a<$core.int>(2, _omitFieldNames ? '' : 'currentEpoch', $pb.PbFieldType.O3)
    ..a<$core.int>(3, _omitFieldNames ? '' : 'totalEpochs', $pb.PbFieldType.O3)
    ..a<$core.double>(4, _omitFieldNames ? '' : 'loss', $pb.PbFieldType.OD)
    ..pc<TrainingDimension>(5, _omitFieldNames ? '' : 'dimensions', $pb.PbFieldType.PM, subBuilder: TrainingDimension.create)
    ..aOS(6, _omitFieldNames ? '' : 'statusText')
    ..hasRequiredFields = false
  ;

  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  TrainingStatusReply clone() => TrainingStatusReply()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  TrainingStatusReply copyWith(void Function(TrainingStatusReply) updates) => super.copyWith((message) => updates(message as TrainingStatusReply)) as TrainingStatusReply;

  $pb.BuilderInfo get info_ => _i;

  @$core.pragma('dart2js:noInline')
  static TrainingStatusReply create() => TrainingStatusReply._();
  TrainingStatusReply createEmptyInstance() => create();
  static $pb.PbList<TrainingStatusReply> createRepeated() => $pb.PbList<TrainingStatusReply>();
  @$core.pragma('dart2js:noInline')
  static TrainingStatusReply getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<TrainingStatusReply>(create);
  static TrainingStatusReply? _defaultInstance;

  @$pb.TagNumber(1)
  $core.bool get isTraining => $_getBF(0);
  @$pb.TagNumber(1)
  set isTraining($core.bool v) { $_setBool(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasIsTraining() => $_has(0);
  @$pb.TagNumber(1)
  void clearIsTraining() => $_clearField(1);

  @$pb.TagNumber(2)
  $core.int get currentEpoch => $_getIZ(1);
  @$pb.TagNumber(2)
  set currentEpoch($core.int v) { $_setSignedInt32(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasCurrentEpoch() => $_has(1);
  @$pb.TagNumber(2)
  void clearCurrentEpoch() => $_clearField(2);

  @$pb.TagNumber(3)
  $core.int get totalEpochs => $_getIZ(2);
  @$pb.TagNumber(3)
  set totalEpochs($core.int v) { $_setSignedInt32(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasTotalEpochs() => $_has(2);
  @$pb.TagNumber(3)
  void clearTotalEpochs() => $_clearField(3);

  @$pb.TagNumber(4)
  $core.double get loss => $_getN(3);
  @$pb.TagNumber(4)
  set loss($core.double v) { $_setDouble(3, v); }
  @$pb.TagNumber(4)
  $core.bool hasLoss() => $_has(3);
  @$pb.TagNumber(4)
  void clearLoss() => $_clearField(4);

  @$pb.TagNumber(5)
  $pb.PbList<TrainingDimension> get dimensions => $_getList(4);

  @$pb.TagNumber(6)
  $core.String get statusText => $_getSZ(5);
  @$pb.TagNumber(6)
  set statusText($core.String v) { $_setString(5, v); }
  @$pb.TagNumber(6)
  $core.bool hasStatusText() => $_has(5);
  @$pb.TagNumber(6)
  void clearStatusText() => $_clearField(6);
}

/// ===== 插件列表 =====
class PluginInfo extends $pb.GeneratedMessage {
  factory PluginInfo({
    $core.String? name,
    $core.String? description,
    $core.String? version,
    $core.bool? enabled,
    $core.String? category,
  }) {
    final $result = create();
    if (name != null) {
      $result.name = name;
    }
    if (description != null) {
      $result.description = description;
    }
    if (version != null) {
      $result.version = version;
    }
    if (enabled != null) {
      $result.enabled = enabled;
    }
    if (category != null) {
      $result.category = category;
    }
    return $result;
  }
  PluginInfo._() : super();
  factory PluginInfo.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory PluginInfo.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);

  static final $pb.BuilderInfo _i = $pb.BuilderInfo(_omitMessageNames ? '' : 'PluginInfo', package: const $pb.PackageName(_omitMessageNames ? '' : 'xiaoling'), createEmptyInstance: create)
    ..aOS(1, _omitFieldNames ? '' : 'name')
    ..aOS(2, _omitFieldNames ? '' : 'description')
    ..aOS(3, _omitFieldNames ? '' : 'version')
    ..aOB(4, _omitFieldNames ? '' : 'enabled')
    ..aOS(5, _omitFieldNames ? '' : 'category')
    ..hasRequiredFields = false
  ;

  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  PluginInfo clone() => PluginInfo()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  PluginInfo copyWith(void Function(PluginInfo) updates) => super.copyWith((message) => updates(message as PluginInfo)) as PluginInfo;

  $pb.BuilderInfo get info_ => _i;

  @$core.pragma('dart2js:noInline')
  static PluginInfo create() => PluginInfo._();
  PluginInfo createEmptyInstance() => create();
  static $pb.PbList<PluginInfo> createRepeated() => $pb.PbList<PluginInfo>();
  @$core.pragma('dart2js:noInline')
  static PluginInfo getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<PluginInfo>(create);
  static PluginInfo? _defaultInstance;

  @$pb.TagNumber(1)
  $core.String get name => $_getSZ(0);
  @$pb.TagNumber(1)
  set name($core.String v) { $_setString(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasName() => $_has(0);
  @$pb.TagNumber(1)
  void clearName() => $_clearField(1);

  @$pb.TagNumber(2)
  $core.String get description => $_getSZ(1);
  @$pb.TagNumber(2)
  set description($core.String v) { $_setString(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasDescription() => $_has(1);
  @$pb.TagNumber(2)
  void clearDescription() => $_clearField(2);

  @$pb.TagNumber(3)
  $core.String get version => $_getSZ(2);
  @$pb.TagNumber(3)
  set version($core.String v) { $_setString(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasVersion() => $_has(2);
  @$pb.TagNumber(3)
  void clearVersion() => $_clearField(3);

  @$pb.TagNumber(4)
  $core.bool get enabled => $_getBF(3);
  @$pb.TagNumber(4)
  set enabled($core.bool v) { $_setBool(3, v); }
  @$pb.TagNumber(4)
  $core.bool hasEnabled() => $_has(3);
  @$pb.TagNumber(4)
  void clearEnabled() => $_clearField(4);

  @$pb.TagNumber(5)
  $core.String get category => $_getSZ(4);
  @$pb.TagNumber(5)
  set category($core.String v) { $_setString(4, v); }
  @$pb.TagNumber(5)
  $core.bool hasCategory() => $_has(4);
  @$pb.TagNumber(5)
  void clearCategory() => $_clearField(5);
}

class PluginList extends $pb.GeneratedMessage {
  factory PluginList({
    $core.Iterable<PluginInfo>? plugins,
  }) {
    final $result = create();
    if (plugins != null) {
      $result.plugins.addAll(plugins);
    }
    return $result;
  }
  PluginList._() : super();
  factory PluginList.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory PluginList.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);

  static final $pb.BuilderInfo _i = $pb.BuilderInfo(_omitMessageNames ? '' : 'PluginList', package: const $pb.PackageName(_omitMessageNames ? '' : 'xiaoling'), createEmptyInstance: create)
    ..pc<PluginInfo>(1, _omitFieldNames ? '' : 'plugins', $pb.PbFieldType.PM, subBuilder: PluginInfo.create)
    ..hasRequiredFields = false
  ;

  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  PluginList clone() => PluginList()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  PluginList copyWith(void Function(PluginList) updates) => super.copyWith((message) => updates(message as PluginList)) as PluginList;

  $pb.BuilderInfo get info_ => _i;

  @$core.pragma('dart2js:noInline')
  static PluginList create() => PluginList._();
  PluginList createEmptyInstance() => create();
  static $pb.PbList<PluginList> createRepeated() => $pb.PbList<PluginList>();
  @$core.pragma('dart2js:noInline')
  static PluginList getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<PluginList>(create);
  static PluginList? _defaultInstance;

  @$pb.TagNumber(1)
  $pb.PbList<PluginInfo> get plugins => $_getList(0);
}

/// ===== 启动训练请求 / 进度 =====
class TrainingRequest extends $pb.GeneratedMessage {
  factory TrainingRequest({
    $core.int? steps,
    $core.double? learningRate,
    $core.int? batchSize,
    $core.int? loraRank,
    $core.String? datasetName,
  }) {
    final $result = create();
    if (steps != null) {
      $result.steps = steps;
    }
    if (learningRate != null) {
      $result.learningRate = learningRate;
    }
    if (batchSize != null) {
      $result.batchSize = batchSize;
    }
    if (loraRank != null) {
      $result.loraRank = loraRank;
    }
    if (datasetName != null) {
      $result.datasetName = datasetName;
    }
    return $result;
  }
  TrainingRequest._() : super();
  factory TrainingRequest.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory TrainingRequest.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);

  static final $pb.BuilderInfo _i = $pb.BuilderInfo(_omitMessageNames ? '' : 'TrainingRequest', package: const $pb.PackageName(_omitMessageNames ? '' : 'xiaoling'), createEmptyInstance: create)
    ..a<$core.int>(1, _omitFieldNames ? '' : 'steps', $pb.PbFieldType.O3)
    ..a<$core.double>(2, _omitFieldNames ? '' : 'learningRate', $pb.PbFieldType.OD)
    ..a<$core.int>(3, _omitFieldNames ? '' : 'batchSize', $pb.PbFieldType.O3)
    ..a<$core.int>(4, _omitFieldNames ? '' : 'loraRank', $pb.PbFieldType.O3)
    ..aOS(5, _omitFieldNames ? '' : 'datasetName')
    ..hasRequiredFields = false
  ;

  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  TrainingRequest clone() => TrainingRequest()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  TrainingRequest copyWith(void Function(TrainingRequest) updates) => super.copyWith((message) => updates(message as TrainingRequest)) as TrainingRequest;

  $pb.BuilderInfo get info_ => _i;

  @$core.pragma('dart2js:noInline')
  static TrainingRequest create() => TrainingRequest._();
  TrainingRequest createEmptyInstance() => create();
  static $pb.PbList<TrainingRequest> createRepeated() => $pb.PbList<TrainingRequest>();
  @$core.pragma('dart2js:noInline')
  static TrainingRequest getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<TrainingRequest>(create);
  static TrainingRequest? _defaultInstance;

  @$pb.TagNumber(1)
  $core.int get steps => $_getIZ(0);
  @$pb.TagNumber(1)
  set steps($core.int v) { $_setSignedInt32(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasSteps() => $_has(0);
  @$pb.TagNumber(1)
  void clearSteps() => $_clearField(1);

  @$pb.TagNumber(2)
  $core.double get learningRate => $_getN(1);
  @$pb.TagNumber(2)
  set learningRate($core.double v) { $_setDouble(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasLearningRate() => $_has(1);
  @$pb.TagNumber(2)
  void clearLearningRate() => $_clearField(2);

  @$pb.TagNumber(3)
  $core.int get batchSize => $_getIZ(2);
  @$pb.TagNumber(3)
  set batchSize($core.int v) { $_setSignedInt32(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasBatchSize() => $_has(2);
  @$pb.TagNumber(3)
  void clearBatchSize() => $_clearField(3);

  @$pb.TagNumber(4)
  $core.int get loraRank => $_getIZ(3);
  @$pb.TagNumber(4)
  set loraRank($core.int v) { $_setSignedInt32(3, v); }
  @$pb.TagNumber(4)
  $core.bool hasLoraRank() => $_has(3);
  @$pb.TagNumber(4)
  void clearLoraRank() => $_clearField(4);

  @$pb.TagNumber(5)
  $core.String get datasetName => $_getSZ(4);
  @$pb.TagNumber(5)
  set datasetName($core.String v) { $_setString(4, v); }
  @$pb.TagNumber(5)
  $core.bool hasDatasetName() => $_has(4);
  @$pb.TagNumber(5)
  void clearDatasetName() => $_clearField(5);
}

class TrainingProgress extends $pb.GeneratedMessage {
  factory TrainingProgress({
    $core.int? step,
    $core.int? totalSteps,
    $core.double? loss,
    $core.String? status,
  }) {
    final $result = create();
    if (step != null) {
      $result.step = step;
    }
    if (totalSteps != null) {
      $result.totalSteps = totalSteps;
    }
    if (loss != null) {
      $result.loss = loss;
    }
    if (status != null) {
      $result.status = status;
    }
    return $result;
  }
  TrainingProgress._() : super();
  factory TrainingProgress.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory TrainingProgress.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);

  static final $pb.BuilderInfo _i = $pb.BuilderInfo(_omitMessageNames ? '' : 'TrainingProgress', package: const $pb.PackageName(_omitMessageNames ? '' : 'xiaoling'), createEmptyInstance: create)
    ..a<$core.int>(1, _omitFieldNames ? '' : 'step', $pb.PbFieldType.O3)
    ..a<$core.int>(2, _omitFieldNames ? '' : 'totalSteps', $pb.PbFieldType.O3)
    ..a<$core.double>(3, _omitFieldNames ? '' : 'loss', $pb.PbFieldType.OF)
    ..aOS(4, _omitFieldNames ? '' : 'status')
    ..hasRequiredFields = false
  ;

  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  TrainingProgress clone() => TrainingProgress()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  TrainingProgress copyWith(void Function(TrainingProgress) updates) => super.copyWith((message) => updates(message as TrainingProgress)) as TrainingProgress;

  $pb.BuilderInfo get info_ => _i;

  @$core.pragma('dart2js:noInline')
  static TrainingProgress create() => TrainingProgress._();
  TrainingProgress createEmptyInstance() => create();
  static $pb.PbList<TrainingProgress> createRepeated() => $pb.PbList<TrainingProgress>();
  @$core.pragma('dart2js:noInline')
  static TrainingProgress getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<TrainingProgress>(create);
  static TrainingProgress? _defaultInstance;

  @$pb.TagNumber(1)
  $core.int get step => $_getIZ(0);
  @$pb.TagNumber(1)
  set step($core.int v) { $_setSignedInt32(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasStep() => $_has(0);
  @$pb.TagNumber(1)
  void clearStep() => $_clearField(1);

  @$pb.TagNumber(2)
  $core.int get totalSteps => $_getIZ(1);
  @$pb.TagNumber(2)
  set totalSteps($core.int v) { $_setSignedInt32(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasTotalSteps() => $_has(1);
  @$pb.TagNumber(2)
  void clearTotalSteps() => $_clearField(2);

  @$pb.TagNumber(3)
  $core.double get loss => $_getN(2);
  @$pb.TagNumber(3)
  set loss($core.double v) { $_setFloat(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasLoss() => $_has(2);
  @$pb.TagNumber(3)
  void clearLoss() => $_clearField(3);

  @$pb.TagNumber(4)
  $core.String get status => $_getSZ(3);
  @$pb.TagNumber(4)
  set status($core.String v) { $_setString(3, v); }
  @$pb.TagNumber(4)
  $core.bool hasStatus() => $_has(3);
  @$pb.TagNumber(4)
  void clearStatus() => $_clearField(4);
}

class TrainingHistoryEntry extends $pb.GeneratedMessage {
  factory TrainingHistoryEntry({
    $fixnum.Int64? timestamp,
    $core.int? steps,
    $core.double? finalLoss,
    $core.Iterable<$core.double>? lossCurve,
  }) {
    final $result = create();
    if (timestamp != null) {
      $result.timestamp = timestamp;
    }
    if (steps != null) {
      $result.steps = steps;
    }
    if (finalLoss != null) {
      $result.finalLoss = finalLoss;
    }
    if (lossCurve != null) {
      $result.lossCurve.addAll(lossCurve);
    }
    return $result;
  }
  TrainingHistoryEntry._() : super();
  factory TrainingHistoryEntry.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory TrainingHistoryEntry.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);

  static final $pb.BuilderInfo _i = $pb.BuilderInfo(_omitMessageNames ? '' : 'TrainingHistoryEntry', package: const $pb.PackageName(_omitMessageNames ? '' : 'xiaoling'), createEmptyInstance: create)
    ..aInt64(1, _omitFieldNames ? '' : 'timestamp')
    ..a<$core.int>(2, _omitFieldNames ? '' : 'steps', $pb.PbFieldType.O3)
    ..a<$core.double>(3, _omitFieldNames ? '' : 'finalLoss', $pb.PbFieldType.OF)
    ..p<$core.double>(4, _omitFieldNames ? '' : 'lossCurve', $pb.PbFieldType.KF)
    ..hasRequiredFields = false
  ;

  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  TrainingHistoryEntry clone() => TrainingHistoryEntry()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  TrainingHistoryEntry copyWith(void Function(TrainingHistoryEntry) updates) => super.copyWith((message) => updates(message as TrainingHistoryEntry)) as TrainingHistoryEntry;

  $pb.BuilderInfo get info_ => _i;

  @$core.pragma('dart2js:noInline')
  static TrainingHistoryEntry create() => TrainingHistoryEntry._();
  TrainingHistoryEntry createEmptyInstance() => create();
  static $pb.PbList<TrainingHistoryEntry> createRepeated() => $pb.PbList<TrainingHistoryEntry>();
  @$core.pragma('dart2js:noInline')
  static TrainingHistoryEntry getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<TrainingHistoryEntry>(create);
  static TrainingHistoryEntry? _defaultInstance;

  @$pb.TagNumber(1)
  $fixnum.Int64 get timestamp => $_getI64(0);
  @$pb.TagNumber(1)
  set timestamp($fixnum.Int64 v) { $_setInt64(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasTimestamp() => $_has(0);
  @$pb.TagNumber(1)
  void clearTimestamp() => $_clearField(1);

  @$pb.TagNumber(2)
  $core.int get steps => $_getIZ(1);
  @$pb.TagNumber(2)
  set steps($core.int v) { $_setSignedInt32(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasSteps() => $_has(1);
  @$pb.TagNumber(2)
  void clearSteps() => $_clearField(2);

  @$pb.TagNumber(3)
  $core.double get finalLoss => $_getN(2);
  @$pb.TagNumber(3)
  set finalLoss($core.double v) { $_setFloat(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasFinalLoss() => $_has(2);
  @$pb.TagNumber(3)
  void clearFinalLoss() => $_clearField(3);

  @$pb.TagNumber(4)
  $pb.PbList<$core.double> get lossCurve => $_getList(3);
}

class TrainingHistoryReply extends $pb.GeneratedMessage {
  factory TrainingHistoryReply({
    $core.Iterable<TrainingHistoryEntry>? entries,
  }) {
    final $result = create();
    if (entries != null) {
      $result.entries.addAll(entries);
    }
    return $result;
  }
  TrainingHistoryReply._() : super();
  factory TrainingHistoryReply.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory TrainingHistoryReply.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);

  static final $pb.BuilderInfo _i = $pb.BuilderInfo(_omitMessageNames ? '' : 'TrainingHistoryReply', package: const $pb.PackageName(_omitMessageNames ? '' : 'xiaoling'), createEmptyInstance: create)
    ..pc<TrainingHistoryEntry>(1, _omitFieldNames ? '' : 'entries', $pb.PbFieldType.PM, subBuilder: TrainingHistoryEntry.create)
    ..hasRequiredFields = false
  ;

  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  TrainingHistoryReply clone() => TrainingHistoryReply()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  TrainingHistoryReply copyWith(void Function(TrainingHistoryReply) updates) => super.copyWith((message) => updates(message as TrainingHistoryReply)) as TrainingHistoryReply;

  $pb.BuilderInfo get info_ => _i;

  @$core.pragma('dart2js:noInline')
  static TrainingHistoryReply create() => TrainingHistoryReply._();
  TrainingHistoryReply createEmptyInstance() => create();
  static $pb.PbList<TrainingHistoryReply> createRepeated() => $pb.PbList<TrainingHistoryReply>();
  @$core.pragma('dart2js:noInline')
  static TrainingHistoryReply getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<TrainingHistoryReply>(create);
  static TrainingHistoryReply? _defaultInstance;

  @$pb.TagNumber(1)
  $pb.PbList<TrainingHistoryEntry> get entries => $_getList(0);
}

class PluginToggleRequest extends $pb.GeneratedMessage {
  factory PluginToggleRequest({
    $core.String? name,
  }) {
    final $result = create();
    if (name != null) {
      $result.name = name;
    }
    return $result;
  }
  PluginToggleRequest._() : super();
  factory PluginToggleRequest.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory PluginToggleRequest.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);

  static final $pb.BuilderInfo _i = $pb.BuilderInfo(_omitMessageNames ? '' : 'PluginToggleRequest', package: const $pb.PackageName(_omitMessageNames ? '' : 'xiaoling'), createEmptyInstance: create)
    ..aOS(1, _omitFieldNames ? '' : 'name')
    ..hasRequiredFields = false
  ;

  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  PluginToggleRequest clone() => PluginToggleRequest()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  PluginToggleRequest copyWith(void Function(PluginToggleRequest) updates) => super.copyWith((message) => updates(message as PluginToggleRequest)) as PluginToggleRequest;

  $pb.BuilderInfo get info_ => _i;

  @$core.pragma('dart2js:noInline')
  static PluginToggleRequest create() => PluginToggleRequest._();
  PluginToggleRequest createEmptyInstance() => create();
  static $pb.PbList<PluginToggleRequest> createRepeated() => $pb.PbList<PluginToggleRequest>();
  @$core.pragma('dart2js:noInline')
  static PluginToggleRequest getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<PluginToggleRequest>(create);
  static PluginToggleRequest? _defaultInstance;

  @$pb.TagNumber(1)
  $core.String get name => $_getSZ(0);
  @$pb.TagNumber(1)
  set name($core.String v) { $_setString(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasName() => $_has(0);
  @$pb.TagNumber(1)
  void clearName() => $_clearField(1);
}

class DataBlob extends $pb.GeneratedMessage {
  factory DataBlob({
    $core.String? json,
  }) {
    final $result = create();
    if (json != null) {
      $result.json = json;
    }
    return $result;
  }
  DataBlob._() : super();
  factory DataBlob.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory DataBlob.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);

  static final $pb.BuilderInfo _i = $pb.BuilderInfo(_omitMessageNames ? '' : 'DataBlob', package: const $pb.PackageName(_omitMessageNames ? '' : 'xiaoling'), createEmptyInstance: create)
    ..aOS(1, _omitFieldNames ? '' : 'json')
    ..hasRequiredFields = false
  ;

  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  DataBlob clone() => DataBlob()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  DataBlob copyWith(void Function(DataBlob) updates) => super.copyWith((message) => updates(message as DataBlob)) as DataBlob;

  $pb.BuilderInfo get info_ => _i;

  @$core.pragma('dart2js:noInline')
  static DataBlob create() => DataBlob._();
  DataBlob createEmptyInstance() => create();
  static $pb.PbList<DataBlob> createRepeated() => $pb.PbList<DataBlob>();
  @$core.pragma('dart2js:noInline')
  static DataBlob getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<DataBlob>(create);
  static DataBlob? _defaultInstance;

  @$pb.TagNumber(1)
  $core.String get json => $_getSZ(0);
  @$pb.TagNumber(1)
  set json($core.String v) { $_setString(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasJson() => $_has(0);
  @$pb.TagNumber(1)
  void clearJson() => $_clearField(1);
}

/// ===== 硬件检测 =====
class HardwareInfo extends $pb.GeneratedMessage {
  factory HardwareInfo({
    $core.double? vramGb,
    $core.double? ramGb,
    $core.int? cpuCores,
    $core.double? diskFreeGb,
    $core.String? gpuName,
    $core.String? platform,
    $core.bool? hasCuda,
    $core.bool? hasMetal,
  }) {
    final $result = create();
    if (vramGb != null) {
      $result.vramGb = vramGb;
    }
    if (ramGb != null) {
      $result.ramGb = ramGb;
    }
    if (cpuCores != null) {
      $result.cpuCores = cpuCores;
    }
    if (diskFreeGb != null) {
      $result.diskFreeGb = diskFreeGb;
    }
    if (gpuName != null) {
      $result.gpuName = gpuName;
    }
    if (platform != null) {
      $result.platform = platform;
    }
    if (hasCuda != null) {
      $result.hasCuda = hasCuda;
    }
    if (hasMetal != null) {
      $result.hasMetal = hasMetal;
    }
    return $result;
  }
  HardwareInfo._() : super();
  factory HardwareInfo.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory HardwareInfo.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);

  static final $pb.BuilderInfo _i = $pb.BuilderInfo(_omitMessageNames ? '' : 'HardwareInfo', package: const $pb.PackageName(_omitMessageNames ? '' : 'xiaoling'), createEmptyInstance: create)
    ..a<$core.double>(1, _omitFieldNames ? '' : 'vramGb', $pb.PbFieldType.OD)
    ..a<$core.double>(2, _omitFieldNames ? '' : 'ramGb', $pb.PbFieldType.OD)
    ..a<$core.int>(3, _omitFieldNames ? '' : 'cpuCores', $pb.PbFieldType.O3)
    ..a<$core.double>(4, _omitFieldNames ? '' : 'diskFreeGb', $pb.PbFieldType.OD)
    ..aOS(5, _omitFieldNames ? '' : 'gpuName')
    ..aOS(6, _omitFieldNames ? '' : 'platform')
    ..aOB(7, _omitFieldNames ? '' : 'hasCuda')
    ..aOB(8, _omitFieldNames ? '' : 'hasMetal')
    ..hasRequiredFields = false
  ;

  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  HardwareInfo clone() => HardwareInfo()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  HardwareInfo copyWith(void Function(HardwareInfo) updates) => super.copyWith((message) => updates(message as HardwareInfo)) as HardwareInfo;

  $pb.BuilderInfo get info_ => _i;

  @$core.pragma('dart2js:noInline')
  static HardwareInfo create() => HardwareInfo._();
  HardwareInfo createEmptyInstance() => create();
  static $pb.PbList<HardwareInfo> createRepeated() => $pb.PbList<HardwareInfo>();
  @$core.pragma('dart2js:noInline')
  static HardwareInfo getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<HardwareInfo>(create);
  static HardwareInfo? _defaultInstance;

  @$pb.TagNumber(1)
  $core.double get vramGb => $_getN(0);
  @$pb.TagNumber(1)
  set vramGb($core.double v) { $_setDouble(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasVramGb() => $_has(0);
  @$pb.TagNumber(1)
  void clearVramGb() => $_clearField(1);

  @$pb.TagNumber(2)
  $core.double get ramGb => $_getN(1);
  @$pb.TagNumber(2)
  set ramGb($core.double v) { $_setDouble(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasRamGb() => $_has(1);
  @$pb.TagNumber(2)
  void clearRamGb() => $_clearField(2);

  @$pb.TagNumber(3)
  $core.int get cpuCores => $_getIZ(2);
  @$pb.TagNumber(3)
  set cpuCores($core.int v) { $_setSignedInt32(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasCpuCores() => $_has(2);
  @$pb.TagNumber(3)
  void clearCpuCores() => $_clearField(3);

  @$pb.TagNumber(4)
  $core.double get diskFreeGb => $_getN(3);
  @$pb.TagNumber(4)
  set diskFreeGb($core.double v) { $_setDouble(3, v); }
  @$pb.TagNumber(4)
  $core.bool hasDiskFreeGb() => $_has(3);
  @$pb.TagNumber(4)
  void clearDiskFreeGb() => $_clearField(4);

  @$pb.TagNumber(5)
  $core.String get gpuName => $_getSZ(4);
  @$pb.TagNumber(5)
  set gpuName($core.String v) { $_setString(4, v); }
  @$pb.TagNumber(5)
  $core.bool hasGpuName() => $_has(4);
  @$pb.TagNumber(5)
  void clearGpuName() => $_clearField(5);

  @$pb.TagNumber(6)
  $core.String get platform => $_getSZ(5);
  @$pb.TagNumber(6)
  set platform($core.String v) { $_setString(5, v); }
  @$pb.TagNumber(6)
  $core.bool hasPlatform() => $_has(5);
  @$pb.TagNumber(6)
  void clearPlatform() => $_clearField(6);

  @$pb.TagNumber(7)
  $core.bool get hasCuda => $_getBF(6);
  @$pb.TagNumber(7)
  set hasCuda($core.bool v) { $_setBool(6, v); }
  @$pb.TagNumber(7)
  $core.bool hasHasCuda() => $_has(6);
  @$pb.TagNumber(7)
  void clearHasCuda() => $_clearField(7);

  @$pb.TagNumber(8)
  $core.bool get hasMetal => $_getBF(7);
  @$pb.TagNumber(8)
  set hasMetal($core.bool v) { $_setBool(7, v); }
  @$pb.TagNumber(8)
  $core.bool hasHasMetal() => $_has(7);
  @$pb.TagNumber(8)
  void clearHasMetal() => $_clearField(8);
}

class HardwareRequest extends $pb.GeneratedMessage {
  factory HardwareRequest() => create();
  HardwareRequest._() : super();
  factory HardwareRequest.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory HardwareRequest.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);

  static final $pb.BuilderInfo _i = $pb.BuilderInfo(_omitMessageNames ? '' : 'HardwareRequest', package: const $pb.PackageName(_omitMessageNames ? '' : 'xiaoling'), createEmptyInstance: create)
    ..hasRequiredFields = false
  ;

  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  HardwareRequest clone() => HardwareRequest()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  HardwareRequest copyWith(void Function(HardwareRequest) updates) => super.copyWith((message) => updates(message as HardwareRequest)) as HardwareRequest;

  $pb.BuilderInfo get info_ => _i;

  @$core.pragma('dart2js:noInline')
  static HardwareRequest create() => HardwareRequest._();
  HardwareRequest createEmptyInstance() => create();
  static $pb.PbList<HardwareRequest> createRepeated() => $pb.PbList<HardwareRequest>();
  @$core.pragma('dart2js:noInline')
  static HardwareRequest getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<HardwareRequest>(create);
  static HardwareRequest? _defaultInstance;
}

/// ===== 模型商店 =====
class RecommendedModel extends $pb.GeneratedMessage {
  factory RecommendedModel({
    $core.String? name,
    $core.String? params,
    $core.String? quant,
    $core.double? vramGb,
    $core.double? ramGb,
    $core.int? quality,
    $core.String? context,
    $core.double? sizeMb,
    $core.bool? canRun,
    $core.bool? recommended,
  }) {
    final $result = create();
    if (name != null) {
      $result.name = name;
    }
    if (params != null) {
      $result.params = params;
    }
    if (quant != null) {
      $result.quant = quant;
    }
    if (vramGb != null) {
      $result.vramGb = vramGb;
    }
    if (ramGb != null) {
      $result.ramGb = ramGb;
    }
    if (quality != null) {
      $result.quality = quality;
    }
    if (context != null) {
      $result.context = context;
    }
    if (sizeMb != null) {
      $result.sizeMb = sizeMb;
    }
    if (canRun != null) {
      $result.canRun = canRun;
    }
    if (recommended != null) {
      $result.recommended = recommended;
    }
    return $result;
  }
  RecommendedModel._() : super();
  factory RecommendedModel.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory RecommendedModel.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);

  static final $pb.BuilderInfo _i = $pb.BuilderInfo(_omitMessageNames ? '' : 'RecommendedModel', package: const $pb.PackageName(_omitMessageNames ? '' : 'xiaoling'), createEmptyInstance: create)
    ..aOS(1, _omitFieldNames ? '' : 'name')
    ..aOS(2, _omitFieldNames ? '' : 'params')
    ..aOS(3, _omitFieldNames ? '' : 'quant')
    ..a<$core.double>(4, _omitFieldNames ? '' : 'vramGb', $pb.PbFieldType.OD)
    ..a<$core.double>(5, _omitFieldNames ? '' : 'ramGb', $pb.PbFieldType.OD)
    ..a<$core.int>(6, _omitFieldNames ? '' : 'quality', $pb.PbFieldType.O3)
    ..aOS(7, _omitFieldNames ? '' : 'context')
    ..a<$core.double>(8, _omitFieldNames ? '' : 'sizeMb', $pb.PbFieldType.OD)
    ..aOB(9, _omitFieldNames ? '' : 'canRun')
    ..aOB(10, _omitFieldNames ? '' : 'recommended')
    ..hasRequiredFields = false
  ;

  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  RecommendedModel clone() => RecommendedModel()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  RecommendedModel copyWith(void Function(RecommendedModel) updates) => super.copyWith((message) => updates(message as RecommendedModel)) as RecommendedModel;

  $pb.BuilderInfo get info_ => _i;

  @$core.pragma('dart2js:noInline')
  static RecommendedModel create() => RecommendedModel._();
  RecommendedModel createEmptyInstance() => create();
  static $pb.PbList<RecommendedModel> createRepeated() => $pb.PbList<RecommendedModel>();
  @$core.pragma('dart2js:noInline')
  static RecommendedModel getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<RecommendedModel>(create);
  static RecommendedModel? _defaultInstance;

  @$pb.TagNumber(1)
  $core.String get name => $_getSZ(0);
  @$pb.TagNumber(1)
  set name($core.String v) { $_setString(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasName() => $_has(0);
  @$pb.TagNumber(1)
  void clearName() => $_clearField(1);

  @$pb.TagNumber(2)
  $core.String get params => $_getSZ(1);
  @$pb.TagNumber(2)
  set params($core.String v) { $_setString(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasParams() => $_has(1);
  @$pb.TagNumber(2)
  void clearParams() => $_clearField(2);

  @$pb.TagNumber(3)
  $core.String get quant => $_getSZ(2);
  @$pb.TagNumber(3)
  set quant($core.String v) { $_setString(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasQuant() => $_has(2);
  @$pb.TagNumber(3)
  void clearQuant() => $_clearField(3);

  @$pb.TagNumber(4)
  $core.double get vramGb => $_getN(3);
  @$pb.TagNumber(4)
  set vramGb($core.double v) { $_setDouble(3, v); }
  @$pb.TagNumber(4)
  $core.bool hasVramGb() => $_has(3);
  @$pb.TagNumber(4)
  void clearVramGb() => $_clearField(4);

  @$pb.TagNumber(5)
  $core.double get ramGb => $_getN(4);
  @$pb.TagNumber(5)
  set ramGb($core.double v) { $_setDouble(4, v); }
  @$pb.TagNumber(5)
  $core.bool hasRamGb() => $_has(4);
  @$pb.TagNumber(5)
  void clearRamGb() => $_clearField(5);

  @$pb.TagNumber(6)
  $core.int get quality => $_getIZ(5);
  @$pb.TagNumber(6)
  set quality($core.int v) { $_setSignedInt32(5, v); }
  @$pb.TagNumber(6)
  $core.bool hasQuality() => $_has(5);
  @$pb.TagNumber(6)
  void clearQuality() => $_clearField(6);

  @$pb.TagNumber(7)
  $core.String get context => $_getSZ(6);
  @$pb.TagNumber(7)
  set context($core.String v) { $_setString(6, v); }
  @$pb.TagNumber(7)
  $core.bool hasContext() => $_has(6);
  @$pb.TagNumber(7)
  void clearContext() => $_clearField(7);

  @$pb.TagNumber(8)
  $core.double get sizeMb => $_getN(7);
  @$pb.TagNumber(8)
  set sizeMb($core.double v) { $_setDouble(7, v); }
  @$pb.TagNumber(8)
  $core.bool hasSizeMb() => $_has(7);
  @$pb.TagNumber(8)
  void clearSizeMb() => $_clearField(8);

  @$pb.TagNumber(9)
  $core.bool get canRun => $_getBF(8);
  @$pb.TagNumber(9)
  set canRun($core.bool v) { $_setBool(8, v); }
  @$pb.TagNumber(9)
  $core.bool hasCanRun() => $_has(8);
  @$pb.TagNumber(9)
  void clearCanRun() => $_clearField(9);

  @$pb.TagNumber(10)
  $core.bool get recommended => $_getBF(9);
  @$pb.TagNumber(10)
  set recommended($core.bool v) { $_setBool(9, v); }
  @$pb.TagNumber(10)
  $core.bool hasRecommended() => $_has(9);
  @$pb.TagNumber(10)
  void clearRecommended() => $_clearField(10);
}

class RecommendedModelList extends $pb.GeneratedMessage {
  factory RecommendedModelList({
    $core.Iterable<RecommendedModel>? models,
  }) {
    final $result = create();
    if (models != null) {
      $result.models.addAll(models);
    }
    return $result;
  }
  RecommendedModelList._() : super();
  factory RecommendedModelList.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory RecommendedModelList.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);

  static final $pb.BuilderInfo _i = $pb.BuilderInfo(_omitMessageNames ? '' : 'RecommendedModelList', package: const $pb.PackageName(_omitMessageNames ? '' : 'xiaoling'), createEmptyInstance: create)
    ..pc<RecommendedModel>(1, _omitFieldNames ? '' : 'models', $pb.PbFieldType.PM, subBuilder: RecommendedModel.create)
    ..hasRequiredFields = false
  ;

  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  RecommendedModelList clone() => RecommendedModelList()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  RecommendedModelList copyWith(void Function(RecommendedModelList) updates) => super.copyWith((message) => updates(message as RecommendedModelList)) as RecommendedModelList;

  $pb.BuilderInfo get info_ => _i;

  @$core.pragma('dart2js:noInline')
  static RecommendedModelList create() => RecommendedModelList._();
  RecommendedModelList createEmptyInstance() => create();
  static $pb.PbList<RecommendedModelList> createRepeated() => $pb.PbList<RecommendedModelList>();
  @$core.pragma('dart2js:noInline')
  static RecommendedModelList getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<RecommendedModelList>(create);
  static RecommendedModelList? _defaultInstance;

  @$pb.TagNumber(1)
  $pb.PbList<RecommendedModel> get models => $_getList(0);
}

class DownloadRequest extends $pb.GeneratedMessage {
  factory DownloadRequest({
    $core.String? modelName,
    $core.String? quant,
  }) {
    final $result = create();
    if (modelName != null) {
      $result.modelName = modelName;
    }
    if (quant != null) {
      $result.quant = quant;
    }
    return $result;
  }
  DownloadRequest._() : super();
  factory DownloadRequest.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory DownloadRequest.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);

  static final $pb.BuilderInfo _i = $pb.BuilderInfo(_omitMessageNames ? '' : 'DownloadRequest', package: const $pb.PackageName(_omitMessageNames ? '' : 'xiaoling'), createEmptyInstance: create)
    ..aOS(1, _omitFieldNames ? '' : 'modelName')
    ..aOS(2, _omitFieldNames ? '' : 'quant')
    ..hasRequiredFields = false
  ;

  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  DownloadRequest clone() => DownloadRequest()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  DownloadRequest copyWith(void Function(DownloadRequest) updates) => super.copyWith((message) => updates(message as DownloadRequest)) as DownloadRequest;

  $pb.BuilderInfo get info_ => _i;

  @$core.pragma('dart2js:noInline')
  static DownloadRequest create() => DownloadRequest._();
  DownloadRequest createEmptyInstance() => create();
  static $pb.PbList<DownloadRequest> createRepeated() => $pb.PbList<DownloadRequest>();
  @$core.pragma('dart2js:noInline')
  static DownloadRequest getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<DownloadRequest>(create);
  static DownloadRequest? _defaultInstance;

  @$pb.TagNumber(1)
  $core.String get modelName => $_getSZ(0);
  @$pb.TagNumber(1)
  set modelName($core.String v) { $_setString(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasModelName() => $_has(0);
  @$pb.TagNumber(1)
  void clearModelName() => $_clearField(1);

  @$pb.TagNumber(2)
  $core.String get quant => $_getSZ(1);
  @$pb.TagNumber(2)
  set quant($core.String v) { $_setString(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasQuant() => $_has(1);
  @$pb.TagNumber(2)
  void clearQuant() => $_clearField(2);
}

class DownloadProgress extends $pb.GeneratedMessage {
  factory DownloadProgress({
    $core.double? percent,
    $core.double? downloadedMb,
    $core.double? totalMb,
    $core.String? status,
  }) {
    final $result = create();
    if (percent != null) {
      $result.percent = percent;
    }
    if (downloadedMb != null) {
      $result.downloadedMb = downloadedMb;
    }
    if (totalMb != null) {
      $result.totalMb = totalMb;
    }
    if (status != null) {
      $result.status = status;
    }
    return $result;
  }
  DownloadProgress._() : super();
  factory DownloadProgress.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory DownloadProgress.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);

  static final $pb.BuilderInfo _i = $pb.BuilderInfo(_omitMessageNames ? '' : 'DownloadProgress', package: const $pb.PackageName(_omitMessageNames ? '' : 'xiaoling'), createEmptyInstance: create)
    ..a<$core.double>(1, _omitFieldNames ? '' : 'percent', $pb.PbFieldType.OD)
    ..a<$core.double>(2, _omitFieldNames ? '' : 'downloadedMb', $pb.PbFieldType.OD)
    ..a<$core.double>(3, _omitFieldNames ? '' : 'totalMb', $pb.PbFieldType.OD)
    ..aOS(4, _omitFieldNames ? '' : 'status')
    ..hasRequiredFields = false
  ;

  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  DownloadProgress clone() => DownloadProgress()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  DownloadProgress copyWith(void Function(DownloadProgress) updates) => super.copyWith((message) => updates(message as DownloadProgress)) as DownloadProgress;

  $pb.BuilderInfo get info_ => _i;

  @$core.pragma('dart2js:noInline')
  static DownloadProgress create() => DownloadProgress._();
  DownloadProgress createEmptyInstance() => create();
  static $pb.PbList<DownloadProgress> createRepeated() => $pb.PbList<DownloadProgress>();
  @$core.pragma('dart2js:noInline')
  static DownloadProgress getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<DownloadProgress>(create);
  static DownloadProgress? _defaultInstance;

  @$pb.TagNumber(1)
  $core.double get percent => $_getN(0);
  @$pb.TagNumber(1)
  set percent($core.double v) { $_setDouble(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasPercent() => $_has(0);
  @$pb.TagNumber(1)
  void clearPercent() => $_clearField(1);

  @$pb.TagNumber(2)
  $core.double get downloadedMb => $_getN(1);
  @$pb.TagNumber(2)
  set downloadedMb($core.double v) { $_setDouble(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasDownloadedMb() => $_has(1);
  @$pb.TagNumber(2)
  void clearDownloadedMb() => $_clearField(2);

  @$pb.TagNumber(3)
  $core.double get totalMb => $_getN(2);
  @$pb.TagNumber(3)
  set totalMb($core.double v) { $_setDouble(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasTotalMb() => $_has(2);
  @$pb.TagNumber(3)
  void clearTotalMb() => $_clearField(3);

  @$pb.TagNumber(4)
  $core.String get status => $_getSZ(3);
  @$pb.TagNumber(4)
  set status($core.String v) { $_setString(3, v); }
  @$pb.TagNumber(4)
  $core.bool hasStatus() => $_has(3);
  @$pb.TagNumber(4)
  void clearStatus() => $_clearField(4);
}

class ModelNameRequest extends $pb.GeneratedMessage {
  factory ModelNameRequest({
    $core.String? name,
  }) {
    final $result = create();
    if (name != null) {
      $result.name = name;
    }
    return $result;
  }
  ModelNameRequest._() : super();
  factory ModelNameRequest.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory ModelNameRequest.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);

  static final $pb.BuilderInfo _i = $pb.BuilderInfo(_omitMessageNames ? '' : 'ModelNameRequest', package: const $pb.PackageName(_omitMessageNames ? '' : 'xiaoling'), createEmptyInstance: create)
    ..aOS(1, _omitFieldNames ? '' : 'name')
    ..hasRequiredFields = false
  ;

  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  ModelNameRequest clone() => ModelNameRequest()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  ModelNameRequest copyWith(void Function(ModelNameRequest) updates) => super.copyWith((message) => updates(message as ModelNameRequest)) as ModelNameRequest;

  $pb.BuilderInfo get info_ => _i;

  @$core.pragma('dart2js:noInline')
  static ModelNameRequest create() => ModelNameRequest._();
  ModelNameRequest createEmptyInstance() => create();
  static $pb.PbList<ModelNameRequest> createRepeated() => $pb.PbList<ModelNameRequest>();
  @$core.pragma('dart2js:noInline')
  static ModelNameRequest getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<ModelNameRequest>(create);
  static ModelNameRequest? _defaultInstance;

  @$pb.TagNumber(1)
  $core.String get name => $_getSZ(0);
  @$pb.TagNumber(1)
  set name($core.String v) { $_setString(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasName() => $_has(0);
  @$pb.TagNumber(1)
  void clearName() => $_clearField(1);
}

/// ===== 音色 =====
class VoiceInfo extends $pb.GeneratedMessage {
  factory VoiceInfo({
    $core.String? id,
    $core.String? name,
    $core.String? lang,
  }) {
    final $result = create();
    if (id != null) {
      $result.id = id;
    }
    if (name != null) {
      $result.name = name;
    }
    if (lang != null) {
      $result.lang = lang;
    }
    return $result;
  }
  VoiceInfo._() : super();
  factory VoiceInfo.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory VoiceInfo.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);

  static final $pb.BuilderInfo _i = $pb.BuilderInfo(_omitMessageNames ? '' : 'VoiceInfo', package: const $pb.PackageName(_omitMessageNames ? '' : 'xiaoling'), createEmptyInstance: create)
    ..aOS(1, _omitFieldNames ? '' : 'id')
    ..aOS(2, _omitFieldNames ? '' : 'name')
    ..aOS(3, _omitFieldNames ? '' : 'lang')
    ..hasRequiredFields = false
  ;

  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  VoiceInfo clone() => VoiceInfo()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  VoiceInfo copyWith(void Function(VoiceInfo) updates) => super.copyWith((message) => updates(message as VoiceInfo)) as VoiceInfo;

  $pb.BuilderInfo get info_ => _i;

  @$core.pragma('dart2js:noInline')
  static VoiceInfo create() => VoiceInfo._();
  VoiceInfo createEmptyInstance() => create();
  static $pb.PbList<VoiceInfo> createRepeated() => $pb.PbList<VoiceInfo>();
  @$core.pragma('dart2js:noInline')
  static VoiceInfo getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<VoiceInfo>(create);
  static VoiceInfo? _defaultInstance;

  @$pb.TagNumber(1)
  $core.String get id => $_getSZ(0);
  @$pb.TagNumber(1)
  set id($core.String v) { $_setString(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasId() => $_has(0);
  @$pb.TagNumber(1)
  void clearId() => $_clearField(1);

  @$pb.TagNumber(2)
  $core.String get name => $_getSZ(1);
  @$pb.TagNumber(2)
  set name($core.String v) { $_setString(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasName() => $_has(1);
  @$pb.TagNumber(2)
  void clearName() => $_clearField(2);

  @$pb.TagNumber(3)
  $core.String get lang => $_getSZ(2);
  @$pb.TagNumber(3)
  set lang($core.String v) { $_setString(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasLang() => $_has(2);
  @$pb.TagNumber(3)
  void clearLang() => $_clearField(3);
}

class VoiceList extends $pb.GeneratedMessage {
  factory VoiceList({
    $core.Iterable<VoiceInfo>? voices,
  }) {
    final $result = create();
    if (voices != null) {
      $result.voices.addAll(voices);
    }
    return $result;
  }
  VoiceList._() : super();
  factory VoiceList.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory VoiceList.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);

  static final $pb.BuilderInfo _i = $pb.BuilderInfo(_omitMessageNames ? '' : 'VoiceList', package: const $pb.PackageName(_omitMessageNames ? '' : 'xiaoling'), createEmptyInstance: create)
    ..pc<VoiceInfo>(1, _omitFieldNames ? '' : 'voices', $pb.PbFieldType.PM, subBuilder: VoiceInfo.create)
    ..hasRequiredFields = false
  ;

  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  VoiceList clone() => VoiceList()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  VoiceList copyWith(void Function(VoiceList) updates) => super.copyWith((message) => updates(message as VoiceList)) as VoiceList;

  $pb.BuilderInfo get info_ => _i;

  @$core.pragma('dart2js:noInline')
  static VoiceList create() => VoiceList._();
  VoiceList createEmptyInstance() => create();
  static $pb.PbList<VoiceList> createRepeated() => $pb.PbList<VoiceList>();
  @$core.pragma('dart2js:noInline')
  static VoiceList getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<VoiceList>(create);
  static VoiceList? _defaultInstance;

  @$pb.TagNumber(1)
  $pb.PbList<VoiceInfo> get voices => $_getList(0);
}

class VoiceRequest extends $pb.GeneratedMessage {
  factory VoiceRequest({
    $core.String? voiceId,
  }) {
    final $result = create();
    if (voiceId != null) {
      $result.voiceId = voiceId;
    }
    return $result;
  }
  VoiceRequest._() : super();
  factory VoiceRequest.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory VoiceRequest.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);

  static final $pb.BuilderInfo _i = $pb.BuilderInfo(_omitMessageNames ? '' : 'VoiceRequest', package: const $pb.PackageName(_omitMessageNames ? '' : 'xiaoling'), createEmptyInstance: create)
    ..aOS(1, _omitFieldNames ? '' : 'voiceId')
    ..hasRequiredFields = false
  ;

  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  VoiceRequest clone() => VoiceRequest()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  VoiceRequest copyWith(void Function(VoiceRequest) updates) => super.copyWith((message) => updates(message as VoiceRequest)) as VoiceRequest;

  $pb.BuilderInfo get info_ => _i;

  @$core.pragma('dart2js:noInline')
  static VoiceRequest create() => VoiceRequest._();
  VoiceRequest createEmptyInstance() => create();
  static $pb.PbList<VoiceRequest> createRepeated() => $pb.PbList<VoiceRequest>();
  @$core.pragma('dart2js:noInline')
  static VoiceRequest getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<VoiceRequest>(create);
  static VoiceRequest? _defaultInstance;

  @$pb.TagNumber(1)
  $core.String get voiceId => $_getSZ(0);
  @$pb.TagNumber(1)
  set voiceId($core.String v) { $_setString(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasVoiceId() => $_has(0);
  @$pb.TagNumber(1)
  void clearVoiceId() => $_clearField(1);
}

class ReadRequest extends $pb.GeneratedMessage {
  factory ReadRequest({
    $core.String? text,
  }) {
    final $result = create();
    if (text != null) {
      $result.text = text;
    }
    return $result;
  }
  ReadRequest._() : super();
  factory ReadRequest.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory ReadRequest.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);

  static final $pb.BuilderInfo _i = $pb.BuilderInfo(_omitMessageNames ? '' : 'ReadRequest', package: const $pb.PackageName(_omitMessageNames ? '' : 'xiaoling'), createEmptyInstance: create)
    ..aOS(1, _omitFieldNames ? '' : 'text')
    ..hasRequiredFields = false
  ;

  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  ReadRequest clone() => ReadRequest()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  ReadRequest copyWith(void Function(ReadRequest) updates) => super.copyWith((message) => updates(message as ReadRequest)) as ReadRequest;

  $pb.BuilderInfo get info_ => _i;

  @$core.pragma('dart2js:noInline')
  static ReadRequest create() => ReadRequest._();
  ReadRequest createEmptyInstance() => create();
  static $pb.PbList<ReadRequest> createRepeated() => $pb.PbList<ReadRequest>();
  @$core.pragma('dart2js:noInline')
  static ReadRequest getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<ReadRequest>(create);
  static ReadRequest? _defaultInstance;

  @$pb.TagNumber(1)
  $core.String get text => $_getSZ(0);
  @$pb.TagNumber(1)
  set text($core.String v) { $_setString(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasText() => $_has(0);
  @$pb.TagNumber(1)
  void clearText() => $_clearField(1);
}

class AudioChunk extends $pb.GeneratedMessage {
  factory AudioChunk({
    $core.List<$core.int>? data,
    $core.bool? done,
  }) {
    final $result = create();
    if (data != null) {
      $result.data = data;
    }
    if (done != null) {
      $result.done = done;
    }
    return $result;
  }
  AudioChunk._() : super();
  factory AudioChunk.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory AudioChunk.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);

  static final $pb.BuilderInfo _i = $pb.BuilderInfo(_omitMessageNames ? '' : 'AudioChunk', package: const $pb.PackageName(_omitMessageNames ? '' : 'xiaoling'), createEmptyInstance: create)
    ..a<$core.List<$core.int>>(1, _omitFieldNames ? '' : 'data', $pb.PbFieldType.OY)
    ..aOB(2, _omitFieldNames ? '' : 'done')
    ..hasRequiredFields = false
  ;

  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  AudioChunk clone() => AudioChunk()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  AudioChunk copyWith(void Function(AudioChunk) updates) => super.copyWith((message) => updates(message as AudioChunk)) as AudioChunk;

  $pb.BuilderInfo get info_ => _i;

  @$core.pragma('dart2js:noInline')
  static AudioChunk create() => AudioChunk._();
  AudioChunk createEmptyInstance() => create();
  static $pb.PbList<AudioChunk> createRepeated() => $pb.PbList<AudioChunk>();
  @$core.pragma('dart2js:noInline')
  static AudioChunk getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<AudioChunk>(create);
  static AudioChunk? _defaultInstance;

  @$pb.TagNumber(1)
  $core.List<$core.int> get data => $_getN(0);
  @$pb.TagNumber(1)
  set data($core.List<$core.int> v) { $_setBytes(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasData() => $_has(0);
  @$pb.TagNumber(1)
  void clearData() => $_clearField(1);

  @$pb.TagNumber(2)
  $core.bool get done => $_getBF(1);
  @$pb.TagNumber(2)
  set done($core.bool v) { $_setBool(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasDone() => $_has(1);
  @$pb.TagNumber(2)
  void clearDone() => $_clearField(2);
}

/// ===== 设置 =====
class SettingsReply extends $pb.GeneratedMessage {
  factory SettingsReply({
    $core.String? model,
    $core.String? voice,
    $core.String? renderBackend,
    $core.bool? alwaysOnTop,
    $core.bool? autoStart,
    $core.bool? asrEnabled,
    $core.bool? ttsEnabled,
    $core.bool? readAloudMode,
    $core.String? persona,
    $core.String? userName,
  }) {
    final $result = create();
    if (model != null) {
      $result.model = model;
    }
    if (voice != null) {
      $result.voice = voice;
    }
    if (renderBackend != null) {
      $result.renderBackend = renderBackend;
    }
    if (alwaysOnTop != null) {
      $result.alwaysOnTop = alwaysOnTop;
    }
    if (autoStart != null) {
      $result.autoStart = autoStart;
    }
    if (asrEnabled != null) {
      $result.asrEnabled = asrEnabled;
    }
    if (ttsEnabled != null) {
      $result.ttsEnabled = ttsEnabled;
    }
    if (readAloudMode != null) {
      $result.readAloudMode = readAloudMode;
    }
    if (persona != null) {
      $result.persona = persona;
    }
    if (userName != null) {
      $result.userName = userName;
    }
    return $result;
  }
  SettingsReply._() : super();
  factory SettingsReply.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory SettingsReply.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);

  static final $pb.BuilderInfo _i = $pb.BuilderInfo(_omitMessageNames ? '' : 'SettingsReply', package: const $pb.PackageName(_omitMessageNames ? '' : 'xiaoling'), createEmptyInstance: create)
    ..aOS(1, _omitFieldNames ? '' : 'model')
    ..aOS(2, _omitFieldNames ? '' : 'voice')
    ..aOS(3, _omitFieldNames ? '' : 'renderBackend')
    ..aOB(4, _omitFieldNames ? '' : 'alwaysOnTop')
    ..aOB(5, _omitFieldNames ? '' : 'autoStart')
    ..aOB(6, _omitFieldNames ? '' : 'asrEnabled')
    ..aOB(7, _omitFieldNames ? '' : 'ttsEnabled')
    ..aOB(8, _omitFieldNames ? '' : 'readAloudMode')
    ..aOS(9, _omitFieldNames ? '' : 'persona')
    ..aOS(10, _omitFieldNames ? '' : 'userName')
    ..hasRequiredFields = false
  ;

  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  SettingsReply clone() => SettingsReply()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  SettingsReply copyWith(void Function(SettingsReply) updates) => super.copyWith((message) => updates(message as SettingsReply)) as SettingsReply;

  $pb.BuilderInfo get info_ => _i;

  @$core.pragma('dart2js:noInline')
  static SettingsReply create() => SettingsReply._();
  SettingsReply createEmptyInstance() => create();
  static $pb.PbList<SettingsReply> createRepeated() => $pb.PbList<SettingsReply>();
  @$core.pragma('dart2js:noInline')
  static SettingsReply getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<SettingsReply>(create);
  static SettingsReply? _defaultInstance;

  @$pb.TagNumber(1)
  $core.String get model => $_getSZ(0);
  @$pb.TagNumber(1)
  set model($core.String v) { $_setString(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasModel() => $_has(0);
  @$pb.TagNumber(1)
  void clearModel() => $_clearField(1);

  @$pb.TagNumber(2)
  $core.String get voice => $_getSZ(1);
  @$pb.TagNumber(2)
  set voice($core.String v) { $_setString(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasVoice() => $_has(1);
  @$pb.TagNumber(2)
  void clearVoice() => $_clearField(2);

  @$pb.TagNumber(3)
  $core.String get renderBackend => $_getSZ(2);
  @$pb.TagNumber(3)
  set renderBackend($core.String v) { $_setString(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasRenderBackend() => $_has(2);
  @$pb.TagNumber(3)
  void clearRenderBackend() => $_clearField(3);

  @$pb.TagNumber(4)
  $core.bool get alwaysOnTop => $_getBF(3);
  @$pb.TagNumber(4)
  set alwaysOnTop($core.bool v) { $_setBool(3, v); }
  @$pb.TagNumber(4)
  $core.bool hasAlwaysOnTop() => $_has(3);
  @$pb.TagNumber(4)
  void clearAlwaysOnTop() => $_clearField(4);

  @$pb.TagNumber(5)
  $core.bool get autoStart => $_getBF(4);
  @$pb.TagNumber(5)
  set autoStart($core.bool v) { $_setBool(4, v); }
  @$pb.TagNumber(5)
  $core.bool hasAutoStart() => $_has(4);
  @$pb.TagNumber(5)
  void clearAutoStart() => $_clearField(5);

  @$pb.TagNumber(6)
  $core.bool get asrEnabled => $_getBF(5);
  @$pb.TagNumber(6)
  set asrEnabled($core.bool v) { $_setBool(5, v); }
  @$pb.TagNumber(6)
  $core.bool hasAsrEnabled() => $_has(5);
  @$pb.TagNumber(6)
  void clearAsrEnabled() => $_clearField(6);

  @$pb.TagNumber(7)
  $core.bool get ttsEnabled => $_getBF(6);
  @$pb.TagNumber(7)
  set ttsEnabled($core.bool v) { $_setBool(6, v); }
  @$pb.TagNumber(7)
  $core.bool hasTtsEnabled() => $_has(6);
  @$pb.TagNumber(7)
  void clearTtsEnabled() => $_clearField(7);

  @$pb.TagNumber(8)
  $core.bool get readAloudMode => $_getBF(7);
  @$pb.TagNumber(8)
  set readAloudMode($core.bool v) { $_setBool(7, v); }
  @$pb.TagNumber(8)
  $core.bool hasReadAloudMode() => $_has(7);
  @$pb.TagNumber(8)
  void clearReadAloudMode() => $_clearField(8);

  /// 人格预设名（活跃中），对应 config.persona
  @$pb.TagNumber(9)
  $core.String get persona => $_getSZ(8);
  @$pb.TagNumber(9)
  set persona($core.String v) { $_setString(8, v); }
  @$pb.TagNumber(9)
  $core.bool hasPersona() => $_has(8);
  @$pb.TagNumber(9)
  void clearPersona() => $_clearField(9);

  /// 用户名，对应 config.user_name
  @$pb.TagNumber(10)
  $core.String get userName => $_getSZ(9);
  @$pb.TagNumber(10)
  set userName($core.String v) { $_setString(9, v); }
  @$pb.TagNumber(10)
  $core.bool hasUserName() => $_has(9);
  @$pb.TagNumber(10)
  void clearUserName() => $_clearField(10);
}

class SettingsRequest extends $pb.GeneratedMessage {
  factory SettingsRequest({
    $core.String? model,
    $core.String? voice,
    $core.String? renderBackend,
    $core.bool? alwaysOnTop,
    $core.bool? autoStart,
    $core.bool? asrEnabled,
    $core.bool? ttsEnabled,
    $core.bool? readAloudMode,
    $core.String? persona,
    $core.String? userName,
  }) {
    final $result = create();
    if (model != null) {
      $result.model = model;
    }
    if (voice != null) {
      $result.voice = voice;
    }
    if (renderBackend != null) {
      $result.renderBackend = renderBackend;
    }
    if (alwaysOnTop != null) {
      $result.alwaysOnTop = alwaysOnTop;
    }
    if (autoStart != null) {
      $result.autoStart = autoStart;
    }
    if (asrEnabled != null) {
      $result.asrEnabled = asrEnabled;
    }
    if (ttsEnabled != null) {
      $result.ttsEnabled = ttsEnabled;
    }
    if (readAloudMode != null) {
      $result.readAloudMode = readAloudMode;
    }
    if (persona != null) {
      $result.persona = persona;
    }
    if (userName != null) {
      $result.userName = userName;
    }
    return $result;
  }
  SettingsRequest._() : super();
  factory SettingsRequest.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory SettingsRequest.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);

  static final $pb.BuilderInfo _i = $pb.BuilderInfo(_omitMessageNames ? '' : 'SettingsRequest', package: const $pb.PackageName(_omitMessageNames ? '' : 'xiaoling'), createEmptyInstance: create)
    ..aOS(1, _omitFieldNames ? '' : 'model')
    ..aOS(2, _omitFieldNames ? '' : 'voice')
    ..aOS(3, _omitFieldNames ? '' : 'renderBackend')
    ..aOB(4, _omitFieldNames ? '' : 'alwaysOnTop')
    ..aOB(5, _omitFieldNames ? '' : 'autoStart')
    ..aOB(6, _omitFieldNames ? '' : 'asrEnabled')
    ..aOB(7, _omitFieldNames ? '' : 'ttsEnabled')
    ..aOB(8, _omitFieldNames ? '' : 'readAloudMode')
    ..aOS(9, _omitFieldNames ? '' : 'persona')
    ..aOS(10, _omitFieldNames ? '' : 'userName')
    ..hasRequiredFields = false
  ;

  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  SettingsRequest clone() => SettingsRequest()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  SettingsRequest copyWith(void Function(SettingsRequest) updates) => super.copyWith((message) => updates(message as SettingsRequest)) as SettingsRequest;

  $pb.BuilderInfo get info_ => _i;

  @$core.pragma('dart2js:noInline')
  static SettingsRequest create() => SettingsRequest._();
  SettingsRequest createEmptyInstance() => create();
  static $pb.PbList<SettingsRequest> createRepeated() => $pb.PbList<SettingsRequest>();
  @$core.pragma('dart2js:noInline')
  static SettingsRequest getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<SettingsRequest>(create);
  static SettingsRequest? _defaultInstance;

  @$pb.TagNumber(1)
  $core.String get model => $_getSZ(0);
  @$pb.TagNumber(1)
  set model($core.String v) { $_setString(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasModel() => $_has(0);
  @$pb.TagNumber(1)
  void clearModel() => $_clearField(1);

  @$pb.TagNumber(2)
  $core.String get voice => $_getSZ(1);
  @$pb.TagNumber(2)
  set voice($core.String v) { $_setString(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasVoice() => $_has(1);
  @$pb.TagNumber(2)
  void clearVoice() => $_clearField(2);

  @$pb.TagNumber(3)
  $core.String get renderBackend => $_getSZ(2);
  @$pb.TagNumber(3)
  set renderBackend($core.String v) { $_setString(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasRenderBackend() => $_has(2);
  @$pb.TagNumber(3)
  void clearRenderBackend() => $_clearField(3);

  @$pb.TagNumber(4)
  $core.bool get alwaysOnTop => $_getBF(3);
  @$pb.TagNumber(4)
  set alwaysOnTop($core.bool v) { $_setBool(3, v); }
  @$pb.TagNumber(4)
  $core.bool hasAlwaysOnTop() => $_has(3);
  @$pb.TagNumber(4)
  void clearAlwaysOnTop() => $_clearField(4);

  @$pb.TagNumber(5)
  $core.bool get autoStart => $_getBF(4);
  @$pb.TagNumber(5)
  set autoStart($core.bool v) { $_setBool(4, v); }
  @$pb.TagNumber(5)
  $core.bool hasAutoStart() => $_has(4);
  @$pb.TagNumber(5)
  void clearAutoStart() => $_clearField(5);

  @$pb.TagNumber(6)
  $core.bool get asrEnabled => $_getBF(5);
  @$pb.TagNumber(6)
  set asrEnabled($core.bool v) { $_setBool(5, v); }
  @$pb.TagNumber(6)
  $core.bool hasAsrEnabled() => $_has(5);
  @$pb.TagNumber(6)
  void clearAsrEnabled() => $_clearField(6);

  @$pb.TagNumber(7)
  $core.bool get ttsEnabled => $_getBF(6);
  @$pb.TagNumber(7)
  set ttsEnabled($core.bool v) { $_setBool(6, v); }
  @$pb.TagNumber(7)
  $core.bool hasTtsEnabled() => $_has(6);
  @$pb.TagNumber(7)
  void clearTtsEnabled() => $_clearField(7);

  @$pb.TagNumber(8)
  $core.bool get readAloudMode => $_getBF(7);
  @$pb.TagNumber(8)
  set readAloudMode($core.bool v) { $_setBool(7, v); }
  @$pb.TagNumber(8)
  $core.bool hasReadAloudMode() => $_has(7);
  @$pb.TagNumber(8)
  void clearReadAloudMode() => $_clearField(8);

  @$pb.TagNumber(9)
  $core.String get persona => $_getSZ(8);
  @$pb.TagNumber(9)
  set persona($core.String v) { $_setString(8, v); }
  @$pb.TagNumber(9)
  $core.bool hasPersona() => $_has(8);
  @$pb.TagNumber(9)
  void clearPersona() => $_clearField(9);

  @$pb.TagNumber(10)
  $core.String get userName => $_getSZ(9);
  @$pb.TagNumber(10)
  set userName($core.String v) { $_setString(9, v); }
  @$pb.TagNumber(10)
  $core.bool hasUserName() => $_has(9);
  @$pb.TagNumber(10)
  void clearUserName() => $_clearField(10);
}

/// ===== 人格画像（PersonaEngine 快照） =====
class PersonaReply extends $pb.GeneratedMessage {
  factory PersonaReply({
    $core.String? emotion,
    $core.double? emotionIntensity,
    $core.String? relationship,
    $core.double? relationshipScore,
    $core.double? relationshipProgress,
    $core.int? remindersPending,
    $core.String? persona,
    $core.String? userName,
    $core.Iterable<PersonaAxis>? axes,
  }) {
    final $result = create();
    if (emotion != null) {
      $result.emotion = emotion;
    }
    if (emotionIntensity != null) {
      $result.emotionIntensity = emotionIntensity;
    }
    if (relationship != null) {
      $result.relationship = relationship;
    }
    if (relationshipScore != null) {
      $result.relationshipScore = relationshipScore;
    }
    if (relationshipProgress != null) {
      $result.relationshipProgress = relationshipProgress;
    }
    if (remindersPending != null) {
      $result.remindersPending = remindersPending;
    }
    if (persona != null) {
      $result.persona = persona;
    }
    if (userName != null) {
      $result.userName = userName;
    }
    if (axes != null) {
      $result.axes.addAll(axes);
    }
    return $result;
  }
  PersonaReply._() : super();
  factory PersonaReply.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory PersonaReply.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);

  static final $pb.BuilderInfo _i = $pb.BuilderInfo(_omitMessageNames ? '' : 'PersonaReply', package: const $pb.PackageName(_omitMessageNames ? '' : 'xiaoling'), createEmptyInstance: create)
    ..aOS(1, _omitFieldNames ? '' : 'emotion')
    ..a<$core.double>(2, _omitFieldNames ? '' : 'emotionIntensity', $pb.PbFieldType.OD)
    ..aOS(3, _omitFieldNames ? '' : 'relationship')
    ..a<$core.double>(4, _omitFieldNames ? '' : 'relationshipScore', $pb.PbFieldType.OD)
    ..a<$core.double>(5, _omitFieldNames ? '' : 'relationshipProgress', $pb.PbFieldType.OD)
    ..a<$core.int>(6, _omitFieldNames ? '' : 'remindersPending', $pb.PbFieldType.O3)
    ..aOS(7, _omitFieldNames ? '' : 'persona')
    ..aOS(8, _omitFieldNames ? '' : 'userName')
    ..pc<PersonaAxis>(9, _omitFieldNames ? '' : 'axes', $pb.PbFieldType.PM, subBuilder: PersonaAxis.create)
    ..hasRequiredFields = false
  ;

  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  PersonaReply clone() => PersonaReply()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  PersonaReply copyWith(void Function(PersonaReply) updates) => super.copyWith((message) => updates(message as PersonaReply)) as PersonaReply;

  $pb.BuilderInfo get info_ => _i;

  @$core.pragma('dart2js:noInline')
  static PersonaReply create() => PersonaReply._();
  PersonaReply createEmptyInstance() => create();
  static $pb.PbList<PersonaReply> createRepeated() => $pb.PbList<PersonaReply>();
  @$core.pragma('dart2js:noInline')
  static PersonaReply getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<PersonaReply>(create);
  static PersonaReply? _defaultInstance;

  @$pb.TagNumber(1)
  $core.String get emotion => $_getSZ(0);
  @$pb.TagNumber(1)
  set emotion($core.String v) { $_setString(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasEmotion() => $_has(0);
  @$pb.TagNumber(1)
  void clearEmotion() => $_clearField(1);

  @$pb.TagNumber(2)
  $core.double get emotionIntensity => $_getN(1);
  @$pb.TagNumber(2)
  set emotionIntensity($core.double v) { $_setDouble(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasEmotionIntensity() => $_has(1);
  @$pb.TagNumber(2)
  void clearEmotionIntensity() => $_clearField(2);

  @$pb.TagNumber(3)
  $core.String get relationship => $_getSZ(2);
  @$pb.TagNumber(3)
  set relationship($core.String v) { $_setString(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasRelationship() => $_has(2);
  @$pb.TagNumber(3)
  void clearRelationship() => $_clearField(3);

  @$pb.TagNumber(4)
  $core.double get relationshipScore => $_getN(3);
  @$pb.TagNumber(4)
  set relationshipScore($core.double v) { $_setDouble(3, v); }
  @$pb.TagNumber(4)
  $core.bool hasRelationshipScore() => $_has(3);
  @$pb.TagNumber(4)
  void clearRelationshipScore() => $_clearField(4);

  @$pb.TagNumber(5)
  $core.double get relationshipProgress => $_getN(4);
  @$pb.TagNumber(5)
  set relationshipProgress($core.double v) { $_setDouble(4, v); }
  @$pb.TagNumber(5)
  $core.bool hasRelationshipProgress() => $_has(4);
  @$pb.TagNumber(5)
  void clearRelationshipProgress() => $_clearField(5);

  @$pb.TagNumber(6)
  $core.int get remindersPending => $_getIZ(5);
  @$pb.TagNumber(6)
  set remindersPending($core.int v) { $_setSignedInt32(5, v); }
  @$pb.TagNumber(6)
  $core.bool hasRemindersPending() => $_has(5);
  @$pb.TagNumber(6)
  void clearRemindersPending() => $_clearField(6);

  @$pb.TagNumber(7)
  $core.String get persona => $_getSZ(6);
  @$pb.TagNumber(7)
  set persona($core.String v) { $_setString(6, v); }
  @$pb.TagNumber(7)
  $core.bool hasPersona() => $_has(6);
  @$pb.TagNumber(7)
  void clearPersona() => $_clearField(7);

  @$pb.TagNumber(8)
  $core.String get userName => $_getSZ(7);
  @$pb.TagNumber(8)
  set userName($core.String v) { $_setString(7, v); }
  @$pb.TagNumber(8)
  $core.bool hasUserName() => $_has(7);
  @$pb.TagNumber(8)
  void clearUserName() => $_clearField(8);

  /// 五维情绪构成，用于雷达图
  @$pb.TagNumber(9)
  $pb.PbList<PersonaAxis> get axes => $_getList(8);
}

class PersonaAxis extends $pb.GeneratedMessage {
  factory PersonaAxis({
    $core.String? name,
    $core.String? label,
    $core.double? value,
  }) {
    final $result = create();
    if (name != null) {
      $result.name = name;
    }
    if (label != null) {
      $result.label = label;
    }
    if (value != null) {
      $result.value = value;
    }
    return $result;
  }
  PersonaAxis._() : super();
  factory PersonaAxis.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory PersonaAxis.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);

  static final $pb.BuilderInfo _i = $pb.BuilderInfo(_omitMessageNames ? '' : 'PersonaAxis', package: const $pb.PackageName(_omitMessageNames ? '' : 'xiaoling'), createEmptyInstance: create)
    ..aOS(1, _omitFieldNames ? '' : 'name')
    ..aOS(2, _omitFieldNames ? '' : 'label')
    ..a<$core.double>(3, _omitFieldNames ? '' : 'value', $pb.PbFieldType.OD)
    ..hasRequiredFields = false
  ;

  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  PersonaAxis clone() => PersonaAxis()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  PersonaAxis copyWith(void Function(PersonaAxis) updates) => super.copyWith((message) => updates(message as PersonaAxis)) as PersonaAxis;

  $pb.BuilderInfo get info_ => _i;

  @$core.pragma('dart2js:noInline')
  static PersonaAxis create() => PersonaAxis._();
  PersonaAxis createEmptyInstance() => create();
  static $pb.PbList<PersonaAxis> createRepeated() => $pb.PbList<PersonaAxis>();
  @$core.pragma('dart2js:noInline')
  static PersonaAxis getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<PersonaAxis>(create);
  static PersonaAxis? _defaultInstance;

  @$pb.TagNumber(1)
  $core.String get name => $_getSZ(0);
  @$pb.TagNumber(1)
  set name($core.String v) { $_setString(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasName() => $_has(0);
  @$pb.TagNumber(1)
  void clearName() => $_clearField(1);

  @$pb.TagNumber(2)
  $core.String get label => $_getSZ(1);
  @$pb.TagNumber(2)
  set label($core.String v) { $_setString(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasLabel() => $_has(1);
  @$pb.TagNumber(2)
  void clearLabel() => $_clearField(2);

  @$pb.TagNumber(3)
  $core.double get value => $_getN(2);
  @$pb.TagNumber(3)
  set value($core.double v) { $_setDouble(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasValue() => $_has(2);
  @$pb.TagNumber(3)
  void clearValue() => $_clearField(3);
}

/// ===== 人格预设 =====
class PersonaPreset extends $pb.GeneratedMessage {
  factory PersonaPreset({
    $core.String? id,
    $core.String? name,
    $core.String? description,
    $core.String? promptHint,
    $core.bool? builtin,
    $core.bool? active,
  }) {
    final $result = create();
    if (id != null) {
      $result.id = id;
    }
    if (name != null) {
      $result.name = name;
    }
    if (description != null) {
      $result.description = description;
    }
    if (promptHint != null) {
      $result.promptHint = promptHint;
    }
    if (builtin != null) {
      $result.builtin = builtin;
    }
    if (active != null) {
      $result.active = active;
    }
    return $result;
  }
  PersonaPreset._() : super();
  factory PersonaPreset.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory PersonaPreset.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);

  static final $pb.BuilderInfo _i = $pb.BuilderInfo(_omitMessageNames ? '' : 'PersonaPreset', package: const $pb.PackageName(_omitMessageNames ? '' : 'xiaoling'), createEmptyInstance: create)
    ..aOS(1, _omitFieldNames ? '' : 'id')
    ..aOS(2, _omitFieldNames ? '' : 'name')
    ..aOS(3, _omitFieldNames ? '' : 'description')
    ..aOS(4, _omitFieldNames ? '' : 'promptHint')
    ..aOB(5, _omitFieldNames ? '' : 'builtin')
    ..aOB(6, _omitFieldNames ? '' : 'active')
    ..hasRequiredFields = false
  ;

  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  PersonaPreset clone() => PersonaPreset()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  PersonaPreset copyWith(void Function(PersonaPreset) updates) => super.copyWith((message) => updates(message as PersonaPreset)) as PersonaPreset;

  $pb.BuilderInfo get info_ => _i;

  @$core.pragma('dart2js:noInline')
  static PersonaPreset create() => PersonaPreset._();
  PersonaPreset createEmptyInstance() => create();
  static $pb.PbList<PersonaPreset> createRepeated() => $pb.PbList<PersonaPreset>();
  @$core.pragma('dart2js:noInline')
  static PersonaPreset getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<PersonaPreset>(create);
  static PersonaPreset? _defaultInstance;

  @$pb.TagNumber(1)
  $core.String get id => $_getSZ(0);
  @$pb.TagNumber(1)
  set id($core.String v) { $_setString(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasId() => $_has(0);
  @$pb.TagNumber(1)
  void clearId() => $_clearField(1);

  @$pb.TagNumber(2)
  $core.String get name => $_getSZ(1);
  @$pb.TagNumber(2)
  set name($core.String v) { $_setString(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasName() => $_has(1);
  @$pb.TagNumber(2)
  void clearName() => $_clearField(2);

  @$pb.TagNumber(3)
  $core.String get description => $_getSZ(2);
  @$pb.TagNumber(3)
  set description($core.String v) { $_setString(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasDescription() => $_has(2);
  @$pb.TagNumber(3)
  void clearDescription() => $_clearField(3);

  @$pb.TagNumber(4)
  $core.String get promptHint => $_getSZ(3);
  @$pb.TagNumber(4)
  set promptHint($core.String v) { $_setString(3, v); }
  @$pb.TagNumber(4)
  $core.bool hasPromptHint() => $_has(3);
  @$pb.TagNumber(4)
  void clearPromptHint() => $_clearField(4);

  @$pb.TagNumber(5)
  $core.bool get builtin => $_getBF(4);
  @$pb.TagNumber(5)
  set builtin($core.bool v) { $_setBool(4, v); }
  @$pb.TagNumber(5)
  $core.bool hasBuiltin() => $_has(4);
  @$pb.TagNumber(5)
  void clearBuiltin() => $_clearField(5);

  @$pb.TagNumber(6)
  $core.bool get active => $_getBF(5);
  @$pb.TagNumber(6)
  set active($core.bool v) { $_setBool(5, v); }
  @$pb.TagNumber(6)
  $core.bool hasActive() => $_has(5);
  @$pb.TagNumber(6)
  void clearActive() => $_clearField(6);
}

class PersonaList extends $pb.GeneratedMessage {
  factory PersonaList({
    $core.Iterable<PersonaPreset>? presets,
  }) {
    final $result = create();
    if (presets != null) {
      $result.presets.addAll(presets);
    }
    return $result;
  }
  PersonaList._() : super();
  factory PersonaList.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory PersonaList.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);

  static final $pb.BuilderInfo _i = $pb.BuilderInfo(_omitMessageNames ? '' : 'PersonaList', package: const $pb.PackageName(_omitMessageNames ? '' : 'xiaoling'), createEmptyInstance: create)
    ..pc<PersonaPreset>(1, _omitFieldNames ? '' : 'presets', $pb.PbFieldType.PM, subBuilder: PersonaPreset.create)
    ..hasRequiredFields = false
  ;

  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  PersonaList clone() => PersonaList()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  PersonaList copyWith(void Function(PersonaList) updates) => super.copyWith((message) => updates(message as PersonaList)) as PersonaList;

  $pb.BuilderInfo get info_ => _i;

  @$core.pragma('dart2js:noInline')
  static PersonaList create() => PersonaList._();
  PersonaList createEmptyInstance() => create();
  static $pb.PbList<PersonaList> createRepeated() => $pb.PbList<PersonaList>();
  @$core.pragma('dart2js:noInline')
  static PersonaList getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<PersonaList>(create);
  static PersonaList? _defaultInstance;

  @$pb.TagNumber(1)
  $pb.PbList<PersonaPreset> get presets => $_getList(0);
}

class PersonaRequest extends $pb.GeneratedMessage {
  factory PersonaRequest({
    $core.String? id,
    $core.String? name,
    $core.String? description,
    $core.String? promptHint,
  }) {
    final $result = create();
    if (id != null) {
      $result.id = id;
    }
    if (name != null) {
      $result.name = name;
    }
    if (description != null) {
      $result.description = description;
    }
    if (promptHint != null) {
      $result.promptHint = promptHint;
    }
    return $result;
  }
  PersonaRequest._() : super();
  factory PersonaRequest.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory PersonaRequest.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);

  static final $pb.BuilderInfo _i = $pb.BuilderInfo(_omitMessageNames ? '' : 'PersonaRequest', package: const $pb.PackageName(_omitMessageNames ? '' : 'xiaoling'), createEmptyInstance: create)
    ..aOS(1, _omitFieldNames ? '' : 'id')
    ..aOS(2, _omitFieldNames ? '' : 'name')
    ..aOS(3, _omitFieldNames ? '' : 'description')
    ..aOS(4, _omitFieldNames ? '' : 'promptHint')
    ..hasRequiredFields = false
  ;

  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  PersonaRequest clone() => PersonaRequest()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  PersonaRequest copyWith(void Function(PersonaRequest) updates) => super.copyWith((message) => updates(message as PersonaRequest)) as PersonaRequest;

  $pb.BuilderInfo get info_ => _i;

  @$core.pragma('dart2js:noInline')
  static PersonaRequest create() => PersonaRequest._();
  PersonaRequest createEmptyInstance() => create();
  static $pb.PbList<PersonaRequest> createRepeated() => $pb.PbList<PersonaRequest>();
  @$core.pragma('dart2js:noInline')
  static PersonaRequest getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<PersonaRequest>(create);
  static PersonaRequest? _defaultInstance;

  @$pb.TagNumber(1)
  $core.String get id => $_getSZ(0);
  @$pb.TagNumber(1)
  set id($core.String v) { $_setString(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasId() => $_has(0);
  @$pb.TagNumber(1)
  void clearId() => $_clearField(1);

  @$pb.TagNumber(2)
  $core.String get name => $_getSZ(1);
  @$pb.TagNumber(2)
  set name($core.String v) { $_setString(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasName() => $_has(1);
  @$pb.TagNumber(2)
  void clearName() => $_clearField(2);

  @$pb.TagNumber(3)
  $core.String get description => $_getSZ(2);
  @$pb.TagNumber(3)
  set description($core.String v) { $_setString(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasDescription() => $_has(2);
  @$pb.TagNumber(3)
  void clearDescription() => $_clearField(3);

  @$pb.TagNumber(4)
  $core.String get promptHint => $_getSZ(3);
  @$pb.TagNumber(4)
  set promptHint($core.String v) { $_setString(3, v); }
  @$pb.TagNumber(4)
  $core.bool hasPromptHint() => $_has(3);
  @$pb.TagNumber(4)
  void clearPromptHint() => $_clearField(4);
}

/// ===== 提醒队列 =====
class ReminderItem extends $pb.GeneratedMessage {
  factory ReminderItem({
    $core.String? text,
    $core.double? dueAt,
    $core.bool? done,
    $core.double? createdAt,
    $fixnum.Int64? secondsLeft,
  }) {
    final $result = create();
    if (text != null) {
      $result.text = text;
    }
    if (dueAt != null) {
      $result.dueAt = dueAt;
    }
    if (done != null) {
      $result.done = done;
    }
    if (createdAt != null) {
      $result.createdAt = createdAt;
    }
    if (secondsLeft != null) {
      $result.secondsLeft = secondsLeft;
    }
    return $result;
  }
  ReminderItem._() : super();
  factory ReminderItem.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory ReminderItem.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);

  static final $pb.BuilderInfo _i = $pb.BuilderInfo(_omitMessageNames ? '' : 'ReminderItem', package: const $pb.PackageName(_omitMessageNames ? '' : 'xiaoling'), createEmptyInstance: create)
    ..aOS(1, _omitFieldNames ? '' : 'text')
    ..a<$core.double>(2, _omitFieldNames ? '' : 'dueAt', $pb.PbFieldType.OD)
    ..aOB(3, _omitFieldNames ? '' : 'done')
    ..a<$core.double>(4, _omitFieldNames ? '' : 'createdAt', $pb.PbFieldType.OD)
    ..aInt64(5, _omitFieldNames ? '' : 'secondsLeft')
    ..hasRequiredFields = false
  ;

  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  ReminderItem clone() => ReminderItem()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  ReminderItem copyWith(void Function(ReminderItem) updates) => super.copyWith((message) => updates(message as ReminderItem)) as ReminderItem;

  $pb.BuilderInfo get info_ => _i;

  @$core.pragma('dart2js:noInline')
  static ReminderItem create() => ReminderItem._();
  ReminderItem createEmptyInstance() => create();
  static $pb.PbList<ReminderItem> createRepeated() => $pb.PbList<ReminderItem>();
  @$core.pragma('dart2js:noInline')
  static ReminderItem getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<ReminderItem>(create);
  static ReminderItem? _defaultInstance;

  @$pb.TagNumber(1)
  $core.String get text => $_getSZ(0);
  @$pb.TagNumber(1)
  set text($core.String v) { $_setString(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasText() => $_has(0);
  @$pb.TagNumber(1)
  void clearText() => $_clearField(1);

  @$pb.TagNumber(2)
  $core.double get dueAt => $_getN(1);
  @$pb.TagNumber(2)
  set dueAt($core.double v) { $_setDouble(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasDueAt() => $_has(1);
  @$pb.TagNumber(2)
  void clearDueAt() => $_clearField(2);

  @$pb.TagNumber(3)
  $core.bool get done => $_getBF(2);
  @$pb.TagNumber(3)
  set done($core.bool v) { $_setBool(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasDone() => $_has(2);
  @$pb.TagNumber(3)
  void clearDone() => $_clearField(3);

  @$pb.TagNumber(4)
  $core.double get createdAt => $_getN(3);
  @$pb.TagNumber(4)
  set createdAt($core.double v) { $_setDouble(3, v); }
  @$pb.TagNumber(4)
  $core.bool hasCreatedAt() => $_has(3);
  @$pb.TagNumber(4)
  void clearCreatedAt() => $_clearField(4);

  @$pb.TagNumber(5)
  $fixnum.Int64 get secondsLeft => $_getI64(4);
  @$pb.TagNumber(5)
  set secondsLeft($fixnum.Int64 v) { $_setInt64(4, v); }
  @$pb.TagNumber(5)
  $core.bool hasSecondsLeft() => $_has(4);
  @$pb.TagNumber(5)
  void clearSecondsLeft() => $_clearField(5);
}

class ReminderList extends $pb.GeneratedMessage {
  factory ReminderList({
    $core.Iterable<ReminderItem>? items,
    $core.int? unread,
    $core.int? pending,
  }) {
    final $result = create();
    if (items != null) {
      $result.items.addAll(items);
    }
    if (unread != null) {
      $result.unread = unread;
    }
    if (pending != null) {
      $result.pending = pending;
    }
    return $result;
  }
  ReminderList._() : super();
  factory ReminderList.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory ReminderList.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);

  static final $pb.BuilderInfo _i = $pb.BuilderInfo(_omitMessageNames ? '' : 'ReminderList', package: const $pb.PackageName(_omitMessageNames ? '' : 'xiaoling'), createEmptyInstance: create)
    ..pc<ReminderItem>(1, _omitFieldNames ? '' : 'items', $pb.PbFieldType.PM, subBuilder: ReminderItem.create)
    ..a<$core.int>(2, _omitFieldNames ? '' : 'unread', $pb.PbFieldType.O3)
    ..a<$core.int>(3, _omitFieldNames ? '' : 'pending', $pb.PbFieldType.O3)
    ..hasRequiredFields = false
  ;

  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  ReminderList clone() => ReminderList()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  ReminderList copyWith(void Function(ReminderList) updates) => super.copyWith((message) => updates(message as ReminderList)) as ReminderList;

  $pb.BuilderInfo get info_ => _i;

  @$core.pragma('dart2js:noInline')
  static ReminderList create() => ReminderList._();
  ReminderList createEmptyInstance() => create();
  static $pb.PbList<ReminderList> createRepeated() => $pb.PbList<ReminderList>();
  @$core.pragma('dart2js:noInline')
  static ReminderList getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<ReminderList>(create);
  static ReminderList? _defaultInstance;

  @$pb.TagNumber(1)
  $pb.PbList<ReminderItem> get items => $_getList(0);

  @$pb.TagNumber(2)
  $core.int get unread => $_getIZ(1);
  @$pb.TagNumber(2)
  set unread($core.int v) { $_setSignedInt32(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasUnread() => $_has(1);
  @$pb.TagNumber(2)
  void clearUnread() => $_clearField(2);

  @$pb.TagNumber(3)
  $core.int get pending => $_getIZ(2);
  @$pb.TagNumber(3)
  set pending($core.int v) { $_setSignedInt32(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasPending() => $_has(2);
  @$pb.TagNumber(3)
  void clearPending() => $_clearField(3);
}

class ReminderRequest extends $pb.GeneratedMessage {
  factory ReminderRequest({
    $core.double? dueAt,
  }) {
    final $result = create();
    if (dueAt != null) {
      $result.dueAt = dueAt;
    }
    return $result;
  }
  ReminderRequest._() : super();
  factory ReminderRequest.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory ReminderRequest.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);

  static final $pb.BuilderInfo _i = $pb.BuilderInfo(_omitMessageNames ? '' : 'ReminderRequest', package: const $pb.PackageName(_omitMessageNames ? '' : 'xiaoling'), createEmptyInstance: create)
    ..a<$core.double>(1, _omitFieldNames ? '' : 'dueAt', $pb.PbFieldType.OD)
    ..hasRequiredFields = false
  ;

  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  ReminderRequest clone() => ReminderRequest()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  ReminderRequest copyWith(void Function(ReminderRequest) updates) => super.copyWith((message) => updates(message as ReminderRequest)) as ReminderRequest;

  $pb.BuilderInfo get info_ => _i;

  @$core.pragma('dart2js:noInline')
  static ReminderRequest create() => ReminderRequest._();
  ReminderRequest createEmptyInstance() => create();
  static $pb.PbList<ReminderRequest> createRepeated() => $pb.PbList<ReminderRequest>();
  @$core.pragma('dart2js:noInline')
  static ReminderRequest getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<ReminderRequest>(create);
  static ReminderRequest? _defaultInstance;

  @$pb.TagNumber(1)
  $core.double get dueAt => $_getN(0);
  @$pb.TagNumber(1)
  set dueAt($core.double v) { $_setDouble(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasDueAt() => $_has(0);
  @$pb.TagNumber(1)
  void clearDueAt() => $_clearField(1);
}

/// ===== Agent 自主任务 =====
class AgentRequest extends $pb.GeneratedMessage {
  factory AgentRequest({
    $core.String? task,
    $core.String? context,
    $core.bool? autonomous,
    $core.int? maxSteps,
  }) {
    final $result = create();
    if (task != null) {
      $result.task = task;
    }
    if (context != null) {
      $result.context = context;
    }
    if (autonomous != null) {
      $result.autonomous = autonomous;
    }
    if (maxSteps != null) {
      $result.maxSteps = maxSteps;
    }
    return $result;
  }
  AgentRequest._() : super();
  factory AgentRequest.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory AgentRequest.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);

  static final $pb.BuilderInfo _i = $pb.BuilderInfo(_omitMessageNames ? '' : 'AgentRequest', package: const $pb.PackageName(_omitMessageNames ? '' : 'xiaoling'), createEmptyInstance: create)
    ..aOS(1, _omitFieldNames ? '' : 'task')
    ..aOS(2, _omitFieldNames ? '' : 'context')
    ..aOB(3, _omitFieldNames ? '' : 'autonomous')
    ..a<$core.int>(4, _omitFieldNames ? '' : 'maxSteps', $pb.PbFieldType.O3)
    ..hasRequiredFields = false
  ;

  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  AgentRequest clone() => AgentRequest()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  AgentRequest copyWith(void Function(AgentRequest) updates) => super.copyWith((message) => updates(message as AgentRequest)) as AgentRequest;

  $pb.BuilderInfo get info_ => _i;

  @$core.pragma('dart2js:noInline')
  static AgentRequest create() => AgentRequest._();
  AgentRequest createEmptyInstance() => create();
  static $pb.PbList<AgentRequest> createRepeated() => $pb.PbList<AgentRequest>();
  @$core.pragma('dart2js:noInline')
  static AgentRequest getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<AgentRequest>(create);
  static AgentRequest? _defaultInstance;

  @$pb.TagNumber(1)
  $core.String get task => $_getSZ(0);
  @$pb.TagNumber(1)
  set task($core.String v) { $_setString(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasTask() => $_has(0);
  @$pb.TagNumber(1)
  void clearTask() => $_clearField(1);

  @$pb.TagNumber(2)
  $core.String get context => $_getSZ(1);
  @$pb.TagNumber(2)
  set context($core.String v) { $_setString(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasContext() => $_has(1);
  @$pb.TagNumber(2)
  void clearContext() => $_clearField(2);

  @$pb.TagNumber(3)
  $core.bool get autonomous => $_getBF(2);
  @$pb.TagNumber(3)
  set autonomous($core.bool v) { $_setBool(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasAutonomous() => $_has(2);
  @$pb.TagNumber(3)
  void clearAutonomous() => $_clearField(3);

  @$pb.TagNumber(4)
  $core.int get maxSteps => $_getIZ(3);
  @$pb.TagNumber(4)
  set maxSteps($core.int v) { $_setSignedInt32(3, v); }
  @$pb.TagNumber(4)
  $core.bool hasMaxSteps() => $_has(3);
  @$pb.TagNumber(4)
  void clearMaxSteps() => $_clearField(4);
}

class AgentEvent extends $pb.GeneratedMessage {
  factory AgentEvent({
    $core.String? type,
    $core.String? content,
    $core.String? toolName,
    $core.String? toolArgs,
    $core.String? toolResult,
    $core.int? step,
    $core.int? totalSteps,
    $core.bool? done,
    $core.String? error,
  }) {
    final $result = create();
    if (type != null) {
      $result.type = type;
    }
    if (content != null) {
      $result.content = content;
    }
    if (toolName != null) {
      $result.toolName = toolName;
    }
    if (toolArgs != null) {
      $result.toolArgs = toolArgs;
    }
    if (toolResult != null) {
      $result.toolResult = toolResult;
    }
    if (step != null) {
      $result.step = step;
    }
    if (totalSteps != null) {
      $result.totalSteps = totalSteps;
    }
    if (done != null) {
      $result.done = done;
    }
    if (error != null) {
      $result.error = error;
    }
    return $result;
  }
  AgentEvent._() : super();
  factory AgentEvent.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory AgentEvent.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);

  static final $pb.BuilderInfo _i = $pb.BuilderInfo(_omitMessageNames ? '' : 'AgentEvent', package: const $pb.PackageName(_omitMessageNames ? '' : 'xiaoling'), createEmptyInstance: create)
    ..aOS(1, _omitFieldNames ? '' : 'type')
    ..aOS(2, _omitFieldNames ? '' : 'content')
    ..aOS(3, _omitFieldNames ? '' : 'toolName')
    ..aOS(4, _omitFieldNames ? '' : 'toolArgs')
    ..aOS(5, _omitFieldNames ? '' : 'toolResult')
    ..a<$core.int>(6, _omitFieldNames ? '' : 'step', $pb.PbFieldType.O3)
    ..a<$core.int>(7, _omitFieldNames ? '' : 'totalSteps', $pb.PbFieldType.O3)
    ..aOB(8, _omitFieldNames ? '' : 'done')
    ..aOS(9, _omitFieldNames ? '' : 'error')
    ..hasRequiredFields = false
  ;

  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  AgentEvent clone() => AgentEvent()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  AgentEvent copyWith(void Function(AgentEvent) updates) => super.copyWith((message) => updates(message as AgentEvent)) as AgentEvent;

  $pb.BuilderInfo get info_ => _i;

  @$core.pragma('dart2js:noInline')
  static AgentEvent create() => AgentEvent._();
  AgentEvent createEmptyInstance() => create();
  static $pb.PbList<AgentEvent> createRepeated() => $pb.PbList<AgentEvent>();
  @$core.pragma('dart2js:noInline')
  static AgentEvent getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<AgentEvent>(create);
  static AgentEvent? _defaultInstance;

  @$pb.TagNumber(1)
  $core.String get type => $_getSZ(0);
  @$pb.TagNumber(1)
  set type($core.String v) { $_setString(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasType() => $_has(0);
  @$pb.TagNumber(1)
  void clearType() => $_clearField(1);

  @$pb.TagNumber(2)
  $core.String get content => $_getSZ(1);
  @$pb.TagNumber(2)
  set content($core.String v) { $_setString(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasContent() => $_has(1);
  @$pb.TagNumber(2)
  void clearContent() => $_clearField(2);

  @$pb.TagNumber(3)
  $core.String get toolName => $_getSZ(2);
  @$pb.TagNumber(3)
  set toolName($core.String v) { $_setString(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasToolName() => $_has(2);
  @$pb.TagNumber(3)
  void clearToolName() => $_clearField(3);

  @$pb.TagNumber(4)
  $core.String get toolArgs => $_getSZ(3);
  @$pb.TagNumber(4)
  set toolArgs($core.String v) { $_setString(3, v); }
  @$pb.TagNumber(4)
  $core.bool hasToolArgs() => $_has(3);
  @$pb.TagNumber(4)
  void clearToolArgs() => $_clearField(4);

  @$pb.TagNumber(5)
  $core.String get toolResult => $_getSZ(4);
  @$pb.TagNumber(5)
  set toolResult($core.String v) { $_setString(4, v); }
  @$pb.TagNumber(5)
  $core.bool hasToolResult() => $_has(4);
  @$pb.TagNumber(5)
  void clearToolResult() => $_clearField(5);

  @$pb.TagNumber(6)
  $core.int get step => $_getIZ(5);
  @$pb.TagNumber(6)
  set step($core.int v) { $_setSignedInt32(5, v); }
  @$pb.TagNumber(6)
  $core.bool hasStep() => $_has(5);
  @$pb.TagNumber(6)
  void clearStep() => $_clearField(6);

  @$pb.TagNumber(7)
  $core.int get totalSteps => $_getIZ(6);
  @$pb.TagNumber(7)
  set totalSteps($core.int v) { $_setSignedInt32(6, v); }
  @$pb.TagNumber(7)
  $core.bool hasTotalSteps() => $_has(6);
  @$pb.TagNumber(7)
  void clearTotalSteps() => $_clearField(7);

  @$pb.TagNumber(8)
  $core.bool get done => $_getBF(7);
  @$pb.TagNumber(8)
  set done($core.bool v) { $_setBool(7, v); }
  @$pb.TagNumber(8)
  $core.bool hasDone() => $_has(7);
  @$pb.TagNumber(8)
  void clearDone() => $_clearField(8);

  @$pb.TagNumber(9)
  $core.String get error => $_getSZ(8);
  @$pb.TagNumber(9)
  set error($core.String v) { $_setString(8, v); }
  @$pb.TagNumber(9)
  $core.bool hasError() => $_has(8);
  @$pb.TagNumber(9)
  void clearError() => $_clearField(9);
}

/// ===== 终端 =====
class TerminalSession extends $pb.GeneratedMessage {
  factory TerminalSession({
    $core.String? id,
  }) {
    final $result = create();
    if (id != null) {
      $result.id = id;
    }
    return $result;
  }
  TerminalSession._() : super();
  factory TerminalSession.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory TerminalSession.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);

  static final $pb.BuilderInfo _i = $pb.BuilderInfo(_omitMessageNames ? '' : 'TerminalSession', package: const $pb.PackageName(_omitMessageNames ? '' : 'xiaoling'), createEmptyInstance: create)
    ..aOS(1, _omitFieldNames ? '' : 'id')
    ..hasRequiredFields = false
  ;

  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  TerminalSession clone() => TerminalSession()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  TerminalSession copyWith(void Function(TerminalSession) updates) => super.copyWith((message) => updates(message as TerminalSession)) as TerminalSession;

  $pb.BuilderInfo get info_ => _i;

  @$core.pragma('dart2js:noInline')
  static TerminalSession create() => TerminalSession._();
  TerminalSession createEmptyInstance() => create();
  static $pb.PbList<TerminalSession> createRepeated() => $pb.PbList<TerminalSession>();
  @$core.pragma('dart2js:noInline')
  static TerminalSession getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<TerminalSession>(create);
  static TerminalSession? _defaultInstance;

  @$pb.TagNumber(1)
  $core.String get id => $_getSZ(0);
  @$pb.TagNumber(1)
  set id($core.String v) { $_setString(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasId() => $_has(0);
  @$pb.TagNumber(1)
  void clearId() => $_clearField(1);
}

class TerminalInput extends $pb.GeneratedMessage {
  factory TerminalInput({
    $core.String? sessionId,
    $core.String? data,
  }) {
    final $result = create();
    if (sessionId != null) {
      $result.sessionId = sessionId;
    }
    if (data != null) {
      $result.data = data;
    }
    return $result;
  }
  TerminalInput._() : super();
  factory TerminalInput.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory TerminalInput.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);

  static final $pb.BuilderInfo _i = $pb.BuilderInfo(_omitMessageNames ? '' : 'TerminalInput', package: const $pb.PackageName(_omitMessageNames ? '' : 'xiaoling'), createEmptyInstance: create)
    ..aOS(1, _omitFieldNames ? '' : 'sessionId')
    ..aOS(2, _omitFieldNames ? '' : 'data')
    ..hasRequiredFields = false
  ;

  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  TerminalInput clone() => TerminalInput()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  TerminalInput copyWith(void Function(TerminalInput) updates) => super.copyWith((message) => updates(message as TerminalInput)) as TerminalInput;

  $pb.BuilderInfo get info_ => _i;

  @$core.pragma('dart2js:noInline')
  static TerminalInput create() => TerminalInput._();
  TerminalInput createEmptyInstance() => create();
  static $pb.PbList<TerminalInput> createRepeated() => $pb.PbList<TerminalInput>();
  @$core.pragma('dart2js:noInline')
  static TerminalInput getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<TerminalInput>(create);
  static TerminalInput? _defaultInstance;

  @$pb.TagNumber(1)
  $core.String get sessionId => $_getSZ(0);
  @$pb.TagNumber(1)
  set sessionId($core.String v) { $_setString(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasSessionId() => $_has(0);
  @$pb.TagNumber(1)
  void clearSessionId() => $_clearField(1);

  @$pb.TagNumber(2)
  $core.String get data => $_getSZ(1);
  @$pb.TagNumber(2)
  set data($core.String v) { $_setString(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasData() => $_has(1);
  @$pb.TagNumber(2)
  void clearData() => $_clearField(2);
}

class TerminalSessionId extends $pb.GeneratedMessage {
  factory TerminalSessionId({
    $core.String? id,
  }) {
    final $result = create();
    if (id != null) {
      $result.id = id;
    }
    return $result;
  }
  TerminalSessionId._() : super();
  factory TerminalSessionId.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory TerminalSessionId.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);

  static final $pb.BuilderInfo _i = $pb.BuilderInfo(_omitMessageNames ? '' : 'TerminalSessionId', package: const $pb.PackageName(_omitMessageNames ? '' : 'xiaoling'), createEmptyInstance: create)
    ..aOS(1, _omitFieldNames ? '' : 'id')
    ..hasRequiredFields = false
  ;

  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  TerminalSessionId clone() => TerminalSessionId()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  TerminalSessionId copyWith(void Function(TerminalSessionId) updates) => super.copyWith((message) => updates(message as TerminalSessionId)) as TerminalSessionId;

  $pb.BuilderInfo get info_ => _i;

  @$core.pragma('dart2js:noInline')
  static TerminalSessionId create() => TerminalSessionId._();
  TerminalSessionId createEmptyInstance() => create();
  static $pb.PbList<TerminalSessionId> createRepeated() => $pb.PbList<TerminalSessionId>();
  @$core.pragma('dart2js:noInline')
  static TerminalSessionId getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<TerminalSessionId>(create);
  static TerminalSessionId? _defaultInstance;

  @$pb.TagNumber(1)
  $core.String get id => $_getSZ(0);
  @$pb.TagNumber(1)
  set id($core.String v) { $_setString(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasId() => $_has(0);
  @$pb.TagNumber(1)
  void clearId() => $_clearField(1);
}

class TerminalOutput extends $pb.GeneratedMessage {
  factory TerminalOutput({
    $core.String? data,
    $core.bool? closed,
  }) {
    final $result = create();
    if (data != null) {
      $result.data = data;
    }
    if (closed != null) {
      $result.closed = closed;
    }
    return $result;
  }
  TerminalOutput._() : super();
  factory TerminalOutput.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory TerminalOutput.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);

  static final $pb.BuilderInfo _i = $pb.BuilderInfo(_omitMessageNames ? '' : 'TerminalOutput', package: const $pb.PackageName(_omitMessageNames ? '' : 'xiaoling'), createEmptyInstance: create)
    ..aOS(1, _omitFieldNames ? '' : 'data')
    ..aOB(2, _omitFieldNames ? '' : 'closed')
    ..hasRequiredFields = false
  ;

  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  TerminalOutput clone() => TerminalOutput()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  TerminalOutput copyWith(void Function(TerminalOutput) updates) => super.copyWith((message) => updates(message as TerminalOutput)) as TerminalOutput;

  $pb.BuilderInfo get info_ => _i;

  @$core.pragma('dart2js:noInline')
  static TerminalOutput create() => TerminalOutput._();
  TerminalOutput createEmptyInstance() => create();
  static $pb.PbList<TerminalOutput> createRepeated() => $pb.PbList<TerminalOutput>();
  @$core.pragma('dart2js:noInline')
  static TerminalOutput getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<TerminalOutput>(create);
  static TerminalOutput? _defaultInstance;

  @$pb.TagNumber(1)
  $core.String get data => $_getSZ(0);
  @$pb.TagNumber(1)
  set data($core.String v) { $_setString(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasData() => $_has(0);
  @$pb.TagNumber(1)
  void clearData() => $_clearField(1);

  @$pb.TagNumber(2)
  $core.bool get closed => $_getBF(1);
  @$pb.TagNumber(2)
  set closed($core.bool v) { $_setBool(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasClosed() => $_has(1);
  @$pb.TagNumber(2)
  void clearClosed() => $_clearField(2);
}

/// ===== 文件操作 =====
class FileListRequest extends $pb.GeneratedMessage {
  factory FileListRequest({
    $core.String? path,
  }) {
    final $result = create();
    if (path != null) {
      $result.path = path;
    }
    return $result;
  }
  FileListRequest._() : super();
  factory FileListRequest.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory FileListRequest.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);

  static final $pb.BuilderInfo _i = $pb.BuilderInfo(_omitMessageNames ? '' : 'FileListRequest', package: const $pb.PackageName(_omitMessageNames ? '' : 'xiaoling'), createEmptyInstance: create)
    ..aOS(1, _omitFieldNames ? '' : 'path')
    ..hasRequiredFields = false
  ;

  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  FileListRequest clone() => FileListRequest()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  FileListRequest copyWith(void Function(FileListRequest) updates) => super.copyWith((message) => updates(message as FileListRequest)) as FileListRequest;

  $pb.BuilderInfo get info_ => _i;

  @$core.pragma('dart2js:noInline')
  static FileListRequest create() => FileListRequest._();
  FileListRequest createEmptyInstance() => create();
  static $pb.PbList<FileListRequest> createRepeated() => $pb.PbList<FileListRequest>();
  @$core.pragma('dart2js:noInline')
  static FileListRequest getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<FileListRequest>(create);
  static FileListRequest? _defaultInstance;

  @$pb.TagNumber(1)
  $core.String get path => $_getSZ(0);
  @$pb.TagNumber(1)
  set path($core.String v) { $_setString(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasPath() => $_has(0);
  @$pb.TagNumber(1)
  void clearPath() => $_clearField(1);
}

class FileItem extends $pb.GeneratedMessage {
  factory FileItem({
    $core.String? name,
    $core.String? path,
    $core.bool? isDir,
    $fixnum.Int64? size,
    $core.String? modified,
    $core.String? extension_6,
  }) {
    final $result = create();
    if (name != null) {
      $result.name = name;
    }
    if (path != null) {
      $result.path = path;
    }
    if (isDir != null) {
      $result.isDir = isDir;
    }
    if (size != null) {
      $result.size = size;
    }
    if (modified != null) {
      $result.modified = modified;
    }
    if (extension_6 != null) {
      $result.extension_6 = extension_6;
    }
    return $result;
  }
  FileItem._() : super();
  factory FileItem.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory FileItem.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);

  static final $pb.BuilderInfo _i = $pb.BuilderInfo(_omitMessageNames ? '' : 'FileItem', package: const $pb.PackageName(_omitMessageNames ? '' : 'xiaoling'), createEmptyInstance: create)
    ..aOS(1, _omitFieldNames ? '' : 'name')
    ..aOS(2, _omitFieldNames ? '' : 'path')
    ..aOB(3, _omitFieldNames ? '' : 'isDir')
    ..aInt64(4, _omitFieldNames ? '' : 'size')
    ..aOS(5, _omitFieldNames ? '' : 'modified')
    ..aOS(6, _omitFieldNames ? '' : 'extension')
    ..hasRequiredFields = false
  ;

  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  FileItem clone() => FileItem()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  FileItem copyWith(void Function(FileItem) updates) => super.copyWith((message) => updates(message as FileItem)) as FileItem;

  $pb.BuilderInfo get info_ => _i;

  @$core.pragma('dart2js:noInline')
  static FileItem create() => FileItem._();
  FileItem createEmptyInstance() => create();
  static $pb.PbList<FileItem> createRepeated() => $pb.PbList<FileItem>();
  @$core.pragma('dart2js:noInline')
  static FileItem getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<FileItem>(create);
  static FileItem? _defaultInstance;

  @$pb.TagNumber(1)
  $core.String get name => $_getSZ(0);
  @$pb.TagNumber(1)
  set name($core.String v) { $_setString(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasName() => $_has(0);
  @$pb.TagNumber(1)
  void clearName() => $_clearField(1);

  @$pb.TagNumber(2)
  $core.String get path => $_getSZ(1);
  @$pb.TagNumber(2)
  set path($core.String v) { $_setString(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasPath() => $_has(1);
  @$pb.TagNumber(2)
  void clearPath() => $_clearField(2);

  @$pb.TagNumber(3)
  $core.bool get isDir => $_getBF(2);
  @$pb.TagNumber(3)
  set isDir($core.bool v) { $_setBool(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasIsDir() => $_has(2);
  @$pb.TagNumber(3)
  void clearIsDir() => $_clearField(3);

  @$pb.TagNumber(4)
  $fixnum.Int64 get size => $_getI64(3);
  @$pb.TagNumber(4)
  set size($fixnum.Int64 v) { $_setInt64(3, v); }
  @$pb.TagNumber(4)
  $core.bool hasSize() => $_has(3);
  @$pb.TagNumber(4)
  void clearSize() => $_clearField(4);

  @$pb.TagNumber(5)
  $core.String get modified => $_getSZ(4);
  @$pb.TagNumber(5)
  set modified($core.String v) { $_setString(4, v); }
  @$pb.TagNumber(5)
  $core.bool hasModified() => $_has(4);
  @$pb.TagNumber(5)
  void clearModified() => $_clearField(5);

  @$pb.TagNumber(6)
  $core.String get extension_6 => $_getSZ(5);
  @$pb.TagNumber(6)
  set extension_6($core.String v) { $_setString(5, v); }
  @$pb.TagNumber(6)
  $core.bool hasExtension_6() => $_has(5);
  @$pb.TagNumber(6)
  void clearExtension_6() => $_clearField(6);
}

class FileListReply extends $pb.GeneratedMessage {
  factory FileListReply({
    $core.Iterable<FileItem>? items,
    $core.String? currentPath,
    $core.String? parentPath,
  }) {
    final $result = create();
    if (items != null) {
      $result.items.addAll(items);
    }
    if (currentPath != null) {
      $result.currentPath = currentPath;
    }
    if (parentPath != null) {
      $result.parentPath = parentPath;
    }
    return $result;
  }
  FileListReply._() : super();
  factory FileListReply.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory FileListReply.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);

  static final $pb.BuilderInfo _i = $pb.BuilderInfo(_omitMessageNames ? '' : 'FileListReply', package: const $pb.PackageName(_omitMessageNames ? '' : 'xiaoling'), createEmptyInstance: create)
    ..pc<FileItem>(1, _omitFieldNames ? '' : 'items', $pb.PbFieldType.PM, subBuilder: FileItem.create)
    ..aOS(2, _omitFieldNames ? '' : 'currentPath')
    ..aOS(3, _omitFieldNames ? '' : 'parentPath')
    ..hasRequiredFields = false
  ;

  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  FileListReply clone() => FileListReply()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  FileListReply copyWith(void Function(FileListReply) updates) => super.copyWith((message) => updates(message as FileListReply)) as FileListReply;

  $pb.BuilderInfo get info_ => _i;

  @$core.pragma('dart2js:noInline')
  static FileListReply create() => FileListReply._();
  FileListReply createEmptyInstance() => create();
  static $pb.PbList<FileListReply> createRepeated() => $pb.PbList<FileListReply>();
  @$core.pragma('dart2js:noInline')
  static FileListReply getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<FileListReply>(create);
  static FileListReply? _defaultInstance;

  @$pb.TagNumber(1)
  $pb.PbList<FileItem> get items => $_getList(0);

  @$pb.TagNumber(2)
  $core.String get currentPath => $_getSZ(1);
  @$pb.TagNumber(2)
  set currentPath($core.String v) { $_setString(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasCurrentPath() => $_has(1);
  @$pb.TagNumber(2)
  void clearCurrentPath() => $_clearField(2);

  @$pb.TagNumber(3)
  $core.String get parentPath => $_getSZ(2);
  @$pb.TagNumber(3)
  set parentPath($core.String v) { $_setString(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasParentPath() => $_has(2);
  @$pb.TagNumber(3)
  void clearParentPath() => $_clearField(3);
}

class FileReadRequest extends $pb.GeneratedMessage {
  factory FileReadRequest({
    $core.String? path,
  }) {
    final $result = create();
    if (path != null) {
      $result.path = path;
    }
    return $result;
  }
  FileReadRequest._() : super();
  factory FileReadRequest.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory FileReadRequest.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);

  static final $pb.BuilderInfo _i = $pb.BuilderInfo(_omitMessageNames ? '' : 'FileReadRequest', package: const $pb.PackageName(_omitMessageNames ? '' : 'xiaoling'), createEmptyInstance: create)
    ..aOS(1, _omitFieldNames ? '' : 'path')
    ..hasRequiredFields = false
  ;

  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  FileReadRequest clone() => FileReadRequest()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  FileReadRequest copyWith(void Function(FileReadRequest) updates) => super.copyWith((message) => updates(message as FileReadRequest)) as FileReadRequest;

  $pb.BuilderInfo get info_ => _i;

  @$core.pragma('dart2js:noInline')
  static FileReadRequest create() => FileReadRequest._();
  FileReadRequest createEmptyInstance() => create();
  static $pb.PbList<FileReadRequest> createRepeated() => $pb.PbList<FileReadRequest>();
  @$core.pragma('dart2js:noInline')
  static FileReadRequest getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<FileReadRequest>(create);
  static FileReadRequest? _defaultInstance;

  @$pb.TagNumber(1)
  $core.String get path => $_getSZ(0);
  @$pb.TagNumber(1)
  set path($core.String v) { $_setString(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasPath() => $_has(0);
  @$pb.TagNumber(1)
  void clearPath() => $_clearField(1);
}

class FileContent extends $pb.GeneratedMessage {
  factory FileContent({
    $core.String? path,
    $core.String? content,
    $core.String? language,
    $core.int? lines,
    $fixnum.Int64? size,
  }) {
    final $result = create();
    if (path != null) {
      $result.path = path;
    }
    if (content != null) {
      $result.content = content;
    }
    if (language != null) {
      $result.language = language;
    }
    if (lines != null) {
      $result.lines = lines;
    }
    if (size != null) {
      $result.size = size;
    }
    return $result;
  }
  FileContent._() : super();
  factory FileContent.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory FileContent.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);

  static final $pb.BuilderInfo _i = $pb.BuilderInfo(_omitMessageNames ? '' : 'FileContent', package: const $pb.PackageName(_omitMessageNames ? '' : 'xiaoling'), createEmptyInstance: create)
    ..aOS(1, _omitFieldNames ? '' : 'path')
    ..aOS(2, _omitFieldNames ? '' : 'content')
    ..aOS(3, _omitFieldNames ? '' : 'language')
    ..a<$core.int>(4, _omitFieldNames ? '' : 'lines', $pb.PbFieldType.O3)
    ..aInt64(5, _omitFieldNames ? '' : 'size')
    ..hasRequiredFields = false
  ;

  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  FileContent clone() => FileContent()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  FileContent copyWith(void Function(FileContent) updates) => super.copyWith((message) => updates(message as FileContent)) as FileContent;

  $pb.BuilderInfo get info_ => _i;

  @$core.pragma('dart2js:noInline')
  static FileContent create() => FileContent._();
  FileContent createEmptyInstance() => create();
  static $pb.PbList<FileContent> createRepeated() => $pb.PbList<FileContent>();
  @$core.pragma('dart2js:noInline')
  static FileContent getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<FileContent>(create);
  static FileContent? _defaultInstance;

  @$pb.TagNumber(1)
  $core.String get path => $_getSZ(0);
  @$pb.TagNumber(1)
  set path($core.String v) { $_setString(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasPath() => $_has(0);
  @$pb.TagNumber(1)
  void clearPath() => $_clearField(1);

  @$pb.TagNumber(2)
  $core.String get content => $_getSZ(1);
  @$pb.TagNumber(2)
  set content($core.String v) { $_setString(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasContent() => $_has(1);
  @$pb.TagNumber(2)
  void clearContent() => $_clearField(2);

  @$pb.TagNumber(3)
  $core.String get language => $_getSZ(2);
  @$pb.TagNumber(3)
  set language($core.String v) { $_setString(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasLanguage() => $_has(2);
  @$pb.TagNumber(3)
  void clearLanguage() => $_clearField(3);

  @$pb.TagNumber(4)
  $core.int get lines => $_getIZ(3);
  @$pb.TagNumber(4)
  set lines($core.int v) { $_setSignedInt32(3, v); }
  @$pb.TagNumber(4)
  $core.bool hasLines() => $_has(3);
  @$pb.TagNumber(4)
  void clearLines() => $_clearField(4);

  @$pb.TagNumber(5)
  $fixnum.Int64 get size => $_getI64(4);
  @$pb.TagNumber(5)
  set size($fixnum.Int64 v) { $_setInt64(4, v); }
  @$pb.TagNumber(5)
  $core.bool hasSize() => $_has(4);
  @$pb.TagNumber(5)
  void clearSize() => $_clearField(5);
}

class FileWriteRequest extends $pb.GeneratedMessage {
  factory FileWriteRequest({
    $core.String? path,
    $core.String? content,
    $core.bool? append,
  }) {
    final $result = create();
    if (path != null) {
      $result.path = path;
    }
    if (content != null) {
      $result.content = content;
    }
    if (append != null) {
      $result.append = append;
    }
    return $result;
  }
  FileWriteRequest._() : super();
  factory FileWriteRequest.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory FileWriteRequest.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);

  static final $pb.BuilderInfo _i = $pb.BuilderInfo(_omitMessageNames ? '' : 'FileWriteRequest', package: const $pb.PackageName(_omitMessageNames ? '' : 'xiaoling'), createEmptyInstance: create)
    ..aOS(1, _omitFieldNames ? '' : 'path')
    ..aOS(2, _omitFieldNames ? '' : 'content')
    ..aOB(3, _omitFieldNames ? '' : 'append')
    ..hasRequiredFields = false
  ;

  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  FileWriteRequest clone() => FileWriteRequest()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  FileWriteRequest copyWith(void Function(FileWriteRequest) updates) => super.copyWith((message) => updates(message as FileWriteRequest)) as FileWriteRequest;

  $pb.BuilderInfo get info_ => _i;

  @$core.pragma('dart2js:noInline')
  static FileWriteRequest create() => FileWriteRequest._();
  FileWriteRequest createEmptyInstance() => create();
  static $pb.PbList<FileWriteRequest> createRepeated() => $pb.PbList<FileWriteRequest>();
  @$core.pragma('dart2js:noInline')
  static FileWriteRequest getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<FileWriteRequest>(create);
  static FileWriteRequest? _defaultInstance;

  @$pb.TagNumber(1)
  $core.String get path => $_getSZ(0);
  @$pb.TagNumber(1)
  set path($core.String v) { $_setString(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasPath() => $_has(0);
  @$pb.TagNumber(1)
  void clearPath() => $_clearField(1);

  @$pb.TagNumber(2)
  $core.String get content => $_getSZ(1);
  @$pb.TagNumber(2)
  set content($core.String v) { $_setString(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasContent() => $_has(1);
  @$pb.TagNumber(2)
  void clearContent() => $_clearField(2);

  @$pb.TagNumber(3)
  $core.bool get append => $_getBF(2);
  @$pb.TagNumber(3)
  set append($core.bool v) { $_setBool(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasAppend() => $_has(2);
  @$pb.TagNumber(3)
  void clearAppend() => $_clearField(3);
}

/// ===== 代码搜索 =====
class CodeSearchRequest extends $pb.GeneratedMessage {
  factory CodeSearchRequest({
    $core.String? query,
    $core.String? type,
    $core.String? path,
    $core.int? maxResults,
  }) {
    final $result = create();
    if (query != null) {
      $result.query = query;
    }
    if (type != null) {
      $result.type = type;
    }
    if (path != null) {
      $result.path = path;
    }
    if (maxResults != null) {
      $result.maxResults = maxResults;
    }
    return $result;
  }
  CodeSearchRequest._() : super();
  factory CodeSearchRequest.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory CodeSearchRequest.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);

  static final $pb.BuilderInfo _i = $pb.BuilderInfo(_omitMessageNames ? '' : 'CodeSearchRequest', package: const $pb.PackageName(_omitMessageNames ? '' : 'xiaoling'), createEmptyInstance: create)
    ..aOS(1, _omitFieldNames ? '' : 'query')
    ..aOS(2, _omitFieldNames ? '' : 'type')
    ..aOS(3, _omitFieldNames ? '' : 'path')
    ..a<$core.int>(4, _omitFieldNames ? '' : 'maxResults', $pb.PbFieldType.O3)
    ..hasRequiredFields = false
  ;

  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  CodeSearchRequest clone() => CodeSearchRequest()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  CodeSearchRequest copyWith(void Function(CodeSearchRequest) updates) => super.copyWith((message) => updates(message as CodeSearchRequest)) as CodeSearchRequest;

  $pb.BuilderInfo get info_ => _i;

  @$core.pragma('dart2js:noInline')
  static CodeSearchRequest create() => CodeSearchRequest._();
  CodeSearchRequest createEmptyInstance() => create();
  static $pb.PbList<CodeSearchRequest> createRepeated() => $pb.PbList<CodeSearchRequest>();
  @$core.pragma('dart2js:noInline')
  static CodeSearchRequest getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<CodeSearchRequest>(create);
  static CodeSearchRequest? _defaultInstance;

  @$pb.TagNumber(1)
  $core.String get query => $_getSZ(0);
  @$pb.TagNumber(1)
  set query($core.String v) { $_setString(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasQuery() => $_has(0);
  @$pb.TagNumber(1)
  void clearQuery() => $_clearField(1);

  @$pb.TagNumber(2)
  $core.String get type => $_getSZ(1);
  @$pb.TagNumber(2)
  set type($core.String v) { $_setString(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasType() => $_has(1);
  @$pb.TagNumber(2)
  void clearType() => $_clearField(2);

  @$pb.TagNumber(3)
  $core.String get path => $_getSZ(2);
  @$pb.TagNumber(3)
  set path($core.String v) { $_setString(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasPath() => $_has(2);
  @$pb.TagNumber(3)
  void clearPath() => $_clearField(3);

  @$pb.TagNumber(4)
  $core.int get maxResults => $_getIZ(3);
  @$pb.TagNumber(4)
  set maxResults($core.int v) { $_setSignedInt32(3, v); }
  @$pb.TagNumber(4)
  $core.bool hasMaxResults() => $_has(3);
  @$pb.TagNumber(4)
  void clearMaxResults() => $_clearField(4);
}

class CodeMatch extends $pb.GeneratedMessage {
  factory CodeMatch({
    $core.String? file,
    $core.int? line,
    $core.int? column,
    $core.String? text,
    $core.String? symbol,
    $core.String? kind,
  }) {
    final $result = create();
    if (file != null) {
      $result.file = file;
    }
    if (line != null) {
      $result.line = line;
    }
    if (column != null) {
      $result.column = column;
    }
    if (text != null) {
      $result.text = text;
    }
    if (symbol != null) {
      $result.symbol = symbol;
    }
    if (kind != null) {
      $result.kind = kind;
    }
    return $result;
  }
  CodeMatch._() : super();
  factory CodeMatch.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory CodeMatch.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);

  static final $pb.BuilderInfo _i = $pb.BuilderInfo(_omitMessageNames ? '' : 'CodeMatch', package: const $pb.PackageName(_omitMessageNames ? '' : 'xiaoling'), createEmptyInstance: create)
    ..aOS(1, _omitFieldNames ? '' : 'file')
    ..a<$core.int>(2, _omitFieldNames ? '' : 'line', $pb.PbFieldType.O3)
    ..a<$core.int>(3, _omitFieldNames ? '' : 'column', $pb.PbFieldType.O3)
    ..aOS(4, _omitFieldNames ? '' : 'text')
    ..aOS(5, _omitFieldNames ? '' : 'symbol')
    ..aOS(6, _omitFieldNames ? '' : 'kind')
    ..hasRequiredFields = false
  ;

  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  CodeMatch clone() => CodeMatch()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  CodeMatch copyWith(void Function(CodeMatch) updates) => super.copyWith((message) => updates(message as CodeMatch)) as CodeMatch;

  $pb.BuilderInfo get info_ => _i;

  @$core.pragma('dart2js:noInline')
  static CodeMatch create() => CodeMatch._();
  CodeMatch createEmptyInstance() => create();
  static $pb.PbList<CodeMatch> createRepeated() => $pb.PbList<CodeMatch>();
  @$core.pragma('dart2js:noInline')
  static CodeMatch getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<CodeMatch>(create);
  static CodeMatch? _defaultInstance;

  @$pb.TagNumber(1)
  $core.String get file => $_getSZ(0);
  @$pb.TagNumber(1)
  set file($core.String v) { $_setString(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasFile() => $_has(0);
  @$pb.TagNumber(1)
  void clearFile() => $_clearField(1);

  @$pb.TagNumber(2)
  $core.int get line => $_getIZ(1);
  @$pb.TagNumber(2)
  set line($core.int v) { $_setSignedInt32(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasLine() => $_has(1);
  @$pb.TagNumber(2)
  void clearLine() => $_clearField(2);

  @$pb.TagNumber(3)
  $core.int get column => $_getIZ(2);
  @$pb.TagNumber(3)
  set column($core.int v) { $_setSignedInt32(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasColumn() => $_has(2);
  @$pb.TagNumber(3)
  void clearColumn() => $_clearField(3);

  @$pb.TagNumber(4)
  $core.String get text => $_getSZ(3);
  @$pb.TagNumber(4)
  set text($core.String v) { $_setString(3, v); }
  @$pb.TagNumber(4)
  $core.bool hasText() => $_has(3);
  @$pb.TagNumber(4)
  void clearText() => $_clearField(4);

  @$pb.TagNumber(5)
  $core.String get symbol => $_getSZ(4);
  @$pb.TagNumber(5)
  set symbol($core.String v) { $_setString(4, v); }
  @$pb.TagNumber(5)
  $core.bool hasSymbol() => $_has(4);
  @$pb.TagNumber(5)
  void clearSymbol() => $_clearField(5);

  @$pb.TagNumber(6)
  $core.String get kind => $_getSZ(5);
  @$pb.TagNumber(6)
  set kind($core.String v) { $_setString(5, v); }
  @$pb.TagNumber(6)
  $core.bool hasKind() => $_has(5);
  @$pb.TagNumber(6)
  void clearKind() => $_clearField(6);
}

class CodeSearchReply extends $pb.GeneratedMessage {
  factory CodeSearchReply({
    $core.Iterable<CodeMatch>? matches,
    $core.int? total,
    $core.double? elapsedMs,
  }) {
    final $result = create();
    if (matches != null) {
      $result.matches.addAll(matches);
    }
    if (total != null) {
      $result.total = total;
    }
    if (elapsedMs != null) {
      $result.elapsedMs = elapsedMs;
    }
    return $result;
  }
  CodeSearchReply._() : super();
  factory CodeSearchReply.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory CodeSearchReply.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);

  static final $pb.BuilderInfo _i = $pb.BuilderInfo(_omitMessageNames ? '' : 'CodeSearchReply', package: const $pb.PackageName(_omitMessageNames ? '' : 'xiaoling'), createEmptyInstance: create)
    ..pc<CodeMatch>(1, _omitFieldNames ? '' : 'matches', $pb.PbFieldType.PM, subBuilder: CodeMatch.create)
    ..a<$core.int>(2, _omitFieldNames ? '' : 'total', $pb.PbFieldType.O3)
    ..a<$core.double>(3, _omitFieldNames ? '' : 'elapsedMs', $pb.PbFieldType.OD)
    ..hasRequiredFields = false
  ;

  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  CodeSearchReply clone() => CodeSearchReply()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  CodeSearchReply copyWith(void Function(CodeSearchReply) updates) => super.copyWith((message) => updates(message as CodeSearchReply)) as CodeSearchReply;

  $pb.BuilderInfo get info_ => _i;

  @$core.pragma('dart2js:noInline')
  static CodeSearchReply create() => CodeSearchReply._();
  CodeSearchReply createEmptyInstance() => create();
  static $pb.PbList<CodeSearchReply> createRepeated() => $pb.PbList<CodeSearchReply>();
  @$core.pragma('dart2js:noInline')
  static CodeSearchReply getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<CodeSearchReply>(create);
  static CodeSearchReply? _defaultInstance;

  @$pb.TagNumber(1)
  $pb.PbList<CodeMatch> get matches => $_getList(0);

  @$pb.TagNumber(2)
  $core.int get total => $_getIZ(1);
  @$pb.TagNumber(2)
  set total($core.int v) { $_setSignedInt32(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasTotal() => $_has(1);
  @$pb.TagNumber(2)
  void clearTotal() => $_clearField(2);

  @$pb.TagNumber(3)
  $core.double get elapsedMs => $_getN(2);
  @$pb.TagNumber(3)
  set elapsedMs($core.double v) { $_setDouble(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasElapsedMs() => $_has(2);
  @$pb.TagNumber(3)
  void clearElapsedMs() => $_clearField(3);
}

/// ===== 项目上下文 =====
class ProjectFile extends $pb.GeneratedMessage {
  factory ProjectFile({
    $core.String? path,
    $core.String? language,
    $core.int? lines,
  }) {
    final $result = create();
    if (path != null) {
      $result.path = path;
    }
    if (language != null) {
      $result.language = language;
    }
    if (lines != null) {
      $result.lines = lines;
    }
    return $result;
  }
  ProjectFile._() : super();
  factory ProjectFile.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory ProjectFile.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);

  static final $pb.BuilderInfo _i = $pb.BuilderInfo(_omitMessageNames ? '' : 'ProjectFile', package: const $pb.PackageName(_omitMessageNames ? '' : 'xiaoling'), createEmptyInstance: create)
    ..aOS(1, _omitFieldNames ? '' : 'path')
    ..aOS(2, _omitFieldNames ? '' : 'language')
    ..a<$core.int>(3, _omitFieldNames ? '' : 'lines', $pb.PbFieldType.O3)
    ..hasRequiredFields = false
  ;

  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  ProjectFile clone() => ProjectFile()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  ProjectFile copyWith(void Function(ProjectFile) updates) => super.copyWith((message) => updates(message as ProjectFile)) as ProjectFile;

  $pb.BuilderInfo get info_ => _i;

  @$core.pragma('dart2js:noInline')
  static ProjectFile create() => ProjectFile._();
  ProjectFile createEmptyInstance() => create();
  static $pb.PbList<ProjectFile> createRepeated() => $pb.PbList<ProjectFile>();
  @$core.pragma('dart2js:noInline')
  static ProjectFile getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<ProjectFile>(create);
  static ProjectFile? _defaultInstance;

  @$pb.TagNumber(1)
  $core.String get path => $_getSZ(0);
  @$pb.TagNumber(1)
  set path($core.String v) { $_setString(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasPath() => $_has(0);
  @$pb.TagNumber(1)
  void clearPath() => $_clearField(1);

  @$pb.TagNumber(2)
  $core.String get language => $_getSZ(1);
  @$pb.TagNumber(2)
  set language($core.String v) { $_setString(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasLanguage() => $_has(1);
  @$pb.TagNumber(2)
  void clearLanguage() => $_clearField(2);

  @$pb.TagNumber(3)
  $core.int get lines => $_getIZ(2);
  @$pb.TagNumber(3)
  set lines($core.int v) { $_setSignedInt32(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasLines() => $_has(2);
  @$pb.TagNumber(3)
  void clearLines() => $_clearField(3);
}

class ProjectContextReply extends $pb.GeneratedMessage {
  factory ProjectContextReply({
    $core.String? rootPath,
    $core.String? projectName,
    $core.Iterable<ProjectFile>? files,
    $core.int? totalFiles,
    $core.int? totalLines,
    $core.Iterable<$core.String>? languages,
    $core.String? readme,
  }) {
    final $result = create();
    if (rootPath != null) {
      $result.rootPath = rootPath;
    }
    if (projectName != null) {
      $result.projectName = projectName;
    }
    if (files != null) {
      $result.files.addAll(files);
    }
    if (totalFiles != null) {
      $result.totalFiles = totalFiles;
    }
    if (totalLines != null) {
      $result.totalLines = totalLines;
    }
    if (languages != null) {
      $result.languages.addAll(languages);
    }
    if (readme != null) {
      $result.readme = readme;
    }
    return $result;
  }
  ProjectContextReply._() : super();
  factory ProjectContextReply.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory ProjectContextReply.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);

  static final $pb.BuilderInfo _i = $pb.BuilderInfo(_omitMessageNames ? '' : 'ProjectContextReply', package: const $pb.PackageName(_omitMessageNames ? '' : 'xiaoling'), createEmptyInstance: create)
    ..aOS(1, _omitFieldNames ? '' : 'rootPath')
    ..aOS(2, _omitFieldNames ? '' : 'projectName')
    ..pc<ProjectFile>(3, _omitFieldNames ? '' : 'files', $pb.PbFieldType.PM, subBuilder: ProjectFile.create)
    ..a<$core.int>(4, _omitFieldNames ? '' : 'totalFiles', $pb.PbFieldType.O3)
    ..a<$core.int>(5, _omitFieldNames ? '' : 'totalLines', $pb.PbFieldType.O3)
    ..pPS(6, _omitFieldNames ? '' : 'languages')
    ..aOS(7, _omitFieldNames ? '' : 'readme')
    ..hasRequiredFields = false
  ;

  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.deepCopy] instead. '
  'Will be removed in next major version')
  ProjectContextReply clone() => ProjectContextReply()..mergeFromMessage(this);
  @$core.Deprecated(
  'Using this can add significant overhead to your binary. '
  'Use [GeneratedMessageGenericExtensions.rebuild] instead. '
  'Will be removed in next major version')
  ProjectContextReply copyWith(void Function(ProjectContextReply) updates) => super.copyWith((message) => updates(message as ProjectContextReply)) as ProjectContextReply;

  $pb.BuilderInfo get info_ => _i;

  @$core.pragma('dart2js:noInline')
  static ProjectContextReply create() => ProjectContextReply._();
  ProjectContextReply createEmptyInstance() => create();
  static $pb.PbList<ProjectContextReply> createRepeated() => $pb.PbList<ProjectContextReply>();
  @$core.pragma('dart2js:noInline')
  static ProjectContextReply getDefault() => _defaultInstance ??= $pb.GeneratedMessage.$_defaultFor<ProjectContextReply>(create);
  static ProjectContextReply? _defaultInstance;

  @$pb.TagNumber(1)
  $core.String get rootPath => $_getSZ(0);
  @$pb.TagNumber(1)
  set rootPath($core.String v) { $_setString(0, v); }
  @$pb.TagNumber(1)
  $core.bool hasRootPath() => $_has(0);
  @$pb.TagNumber(1)
  void clearRootPath() => $_clearField(1);

  @$pb.TagNumber(2)
  $core.String get projectName => $_getSZ(1);
  @$pb.TagNumber(2)
  set projectName($core.String v) { $_setString(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasProjectName() => $_has(1);
  @$pb.TagNumber(2)
  void clearProjectName() => $_clearField(2);

  @$pb.TagNumber(3)
  $pb.PbList<ProjectFile> get files => $_getList(2);

  @$pb.TagNumber(4)
  $core.int get totalFiles => $_getIZ(3);
  @$pb.TagNumber(4)
  set totalFiles($core.int v) { $_setSignedInt32(3, v); }
  @$pb.TagNumber(4)
  $core.bool hasTotalFiles() => $_has(3);
  @$pb.TagNumber(4)
  void clearTotalFiles() => $_clearField(4);

  @$pb.TagNumber(5)
  $core.int get totalLines => $_getIZ(4);
  @$pb.TagNumber(5)
  set totalLines($core.int v) { $_setSignedInt32(4, v); }
  @$pb.TagNumber(5)
  $core.bool hasTotalLines() => $_has(4);
  @$pb.TagNumber(5)
  void clearTotalLines() => $_clearField(5);

  @$pb.TagNumber(6)
  $pb.PbList<$core.String> get languages => $_getList(5);

  @$pb.TagNumber(7)
  $core.String get readme => $_getSZ(6);
  @$pb.TagNumber(7)
  set readme($core.String v) { $_setString(6, v); }
  @$pb.TagNumber(7)
  $core.bool hasReadme() => $_has(6);
  @$pb.TagNumber(7)
  void clearReadme() => $_clearField(7);
}


const _omitFieldNames = $core.bool.fromEnvironment('protobuf.omit_field_names');
const _omitMessageNames = $core.bool.fromEnvironment('protobuf.omit_message_names');
