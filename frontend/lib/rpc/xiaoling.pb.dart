//
//  Generated code. Do not modify.
//  source: xiaoling.proto
//
// @dart = 2.12

// ignore_for_file: annotate_overrides, camel_case_types, comment_references
// ignore_for_file: constant_identifier_names, library_prefixes
// ignore_for_file: non_constant_identifier_names, prefer_final_fields
// ignore_for_file: unnecessary_import, unnecessary_this, unused_import

import 'dart:core' as $core;

import 'package:fixnum/fixnum.dart' as $fixnum;
import 'package:protobuf/protobuf.dart' as $pb;

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
  void clearText() => clearField(1);
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
  void clearDelta() => clearField(1);

  @$pb.TagNumber(2)
  $core.bool get done => $_getBF(1);
  @$pb.TagNumber(2)
  set done($core.bool v) { $_setBool(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasDone() => $_has(1);
  @$pb.TagNumber(2)
  void clearDone() => clearField(2);

  @$pb.TagNumber(3)
  $core.String get error => $_getSZ(2);
  @$pb.TagNumber(3)
  set error($core.String v) { $_setString(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasError() => $_has(2);
  @$pb.TagNumber(3)
  void clearError() => clearField(3);
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
  void clearOk() => clearField(1);

  @$pb.TagNumber(2)
  $core.String get message => $_getSZ(1);
  @$pb.TagNumber(2)
  set message($core.String v) { $_setString(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasMessage() => $_has(1);
  @$pb.TagNumber(2)
  void clearMessage() => clearField(2);

  @$pb.TagNumber(3)
  $core.String get stage => $_getSZ(2);
  @$pb.TagNumber(3)
  set stage($core.String v) { $_setString(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasStage() => $_has(2);
  @$pb.TagNumber(3)
  void clearStage() => clearField(3);

  @$pb.TagNumber(4)
  $core.String get model => $_getSZ(3);
  @$pb.TagNumber(4)
  set model($core.String v) { $_setString(3, v); }
  @$pb.TagNumber(4)
  $core.bool hasModel() => $_has(3);
  @$pb.TagNumber(4)
  void clearModel() => clearField(4);

  @$pb.TagNumber(5)
  $core.String get backend => $_getSZ(4);
  @$pb.TagNumber(5)
  set backend($core.String v) { $_setString(4, v); }
  @$pb.TagNumber(5)
  $core.bool hasBackend() => $_has(4);
  @$pb.TagNumber(5)
  void clearBackend() => clearField(5);

  @$pb.TagNumber(6)
  $core.double get progress => $_getN(5);
  @$pb.TagNumber(6)
  set progress($core.double v) { $_setDouble(5, v); }
  @$pb.TagNumber(6)
  $core.bool hasProgress() => $_has(5);
  @$pb.TagNumber(6)
  void clearProgress() => clearField(6);

  @$pb.TagNumber(7)
  $core.String get version => $_getSZ(6);
  @$pb.TagNumber(7)
  set version($core.String v) { $_setString(6, v); }
  @$pb.TagNumber(7)
  $core.bool hasVersion() => $_has(6);
  @$pb.TagNumber(7)
  void clearVersion() => clearField(7);
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
  void clearName() => clearField(1);

  @$pb.TagNumber(2)
  $core.String get path => $_getSZ(1);
  @$pb.TagNumber(2)
  set path($core.String v) { $_setString(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasPath() => $_has(1);
  @$pb.TagNumber(2)
  void clearPath() => clearField(2);

  @$pb.TagNumber(3)
  $core.double get sizeMb => $_getN(2);
  @$pb.TagNumber(3)
  set sizeMb($core.double v) { $_setDouble(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasSizeMb() => $_has(2);
  @$pb.TagNumber(3)
  void clearSizeMb() => clearField(3);
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
  $core.List<ModelInfo> get models => $_getList(0);
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
  void clearPath() => clearField(1);
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
  void clearCommand() => clearField(1);
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
  void clearOutput() => clearField(1);
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
  void clearName() => clearField(1);

  @$pb.TagNumber(2)
  $core.String get path => $_getSZ(1);
  @$pb.TagNumber(2)
  set path($core.String v) { $_setString(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasPath() => $_has(1);
  @$pb.TagNumber(2)
  void clearPath() => clearField(2);

  @$pb.TagNumber(3)
  $core.bool get dance => $_getBF(2);
  @$pb.TagNumber(3)
  set dance($core.bool v) { $_setBool(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasDance() => $_has(2);
  @$pb.TagNumber(3)
  void clearDance() => clearField(3);

  @$pb.TagNumber(4)
  $core.bool get idle => $_getBF(3);
  @$pb.TagNumber(4)
  set idle($core.bool v) { $_setBool(3, v); }
  @$pb.TagNumber(4)
  $core.bool hasIdle() => $_has(3);
  @$pb.TagNumber(4)
  void clearIdle() => clearField(4);
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
  $core.List<ActionInfo> get actions => $_getList(0);
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
  void clearPath() => clearField(1);
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
  void clearStage() => clearField(1);

  @$pb.TagNumber(2)
  $core.double get progressPercent => $_getN(1);
  @$pb.TagNumber(2)
  set progressPercent($core.double v) { $_setDouble(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasProgressPercent() => $_has(1);
  @$pb.TagNumber(2)
  void clearProgressPercent() => clearField(2);

  @$pb.TagNumber(3)
  $core.int get totalInteractions => $_getIZ(2);
  @$pb.TagNumber(3)
  set totalInteractions($core.int v) { $_setSignedInt32(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasTotalInteractions() => $_has(2);
  @$pb.TagNumber(3)
  void clearTotalInteractions() => clearField(3);

  @$pb.TagNumber(4)
  $core.int get currentGeneration => $_getIZ(3);
  @$pb.TagNumber(4)
  set currentGeneration($core.int v) { $_setSignedInt32(3, v); }
  @$pb.TagNumber(4)
  $core.bool hasCurrentGeneration() => $_has(3);
  @$pb.TagNumber(4)
  void clearCurrentGeneration() => clearField(4);

  @$pb.TagNumber(5)
  $core.int get totalGenerations => $_getIZ(4);
  @$pb.TagNumber(5)
  set totalGenerations($core.int v) { $_setSignedInt32(4, v); }
  @$pb.TagNumber(5)
  $core.bool hasTotalGenerations() => $_has(4);
  @$pb.TagNumber(5)
  void clearTotalGenerations() => clearField(5);

  @$pb.TagNumber(6)
  $core.String get currentRank => $_getSZ(5);
  @$pb.TagNumber(6)
  set currentRank($core.String v) { $_setString(5, v); }
  @$pb.TagNumber(6)
  $core.bool hasCurrentRank() => $_has(5);
  @$pb.TagNumber(6)
  void clearCurrentRank() => clearField(6);

  @$pb.TagNumber(7)
  $core.String get emotion => $_getSZ(6);
  @$pb.TagNumber(7)
  set emotion($core.String v) { $_setString(6, v); }
  @$pb.TagNumber(7)
  $core.bool hasEmotion() => $_has(6);
  @$pb.TagNumber(7)
  void clearEmotion() => clearField(7);

  @$pb.TagNumber(8)
  $core.bool get trainingPaused => $_getBF(7);
  @$pb.TagNumber(8)
  set trainingPaused($core.bool v) { $_setBool(7, v); }
  @$pb.TagNumber(8)
  $core.bool hasTrainingPaused() => $_has(7);
  @$pb.TagNumber(8)
  void clearTrainingPaused() => clearField(8);

  @$pb.TagNumber(9)
  $core.String get statusText => $_getSZ(8);
  @$pb.TagNumber(9)
  set statusText($core.String v) { $_setString(8, v); }
  @$pb.TagNumber(9)
  $core.bool hasStatusText() => $_has(8);
  @$pb.TagNumber(9)
  void clearStatusText() => clearField(9);
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
  void clearName() => clearField(1);

  @$pb.TagNumber(2)
  $core.double get value => $_getN(1);
  @$pb.TagNumber(2)
  set value($core.double v) { $_setDouble(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasValue() => $_has(1);
  @$pb.TagNumber(2)
  void clearValue() => clearField(2);

  @$pb.TagNumber(3)
  $core.String get label => $_getSZ(2);
  @$pb.TagNumber(3)
  set label($core.String v) { $_setString(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasLabel() => $_has(2);
  @$pb.TagNumber(3)
  void clearLabel() => clearField(3);
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
  void clearIsTraining() => clearField(1);

  @$pb.TagNumber(2)
  $core.int get currentEpoch => $_getIZ(1);
  @$pb.TagNumber(2)
  set currentEpoch($core.int v) { $_setSignedInt32(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasCurrentEpoch() => $_has(1);
  @$pb.TagNumber(2)
  void clearCurrentEpoch() => clearField(2);

  @$pb.TagNumber(3)
  $core.int get totalEpochs => $_getIZ(2);
  @$pb.TagNumber(3)
  set totalEpochs($core.int v) { $_setSignedInt32(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasTotalEpochs() => $_has(2);
  @$pb.TagNumber(3)
  void clearTotalEpochs() => clearField(3);

  @$pb.TagNumber(4)
  $core.double get loss => $_getN(3);
  @$pb.TagNumber(4)
  set loss($core.double v) { $_setDouble(3, v); }
  @$pb.TagNumber(4)
  $core.bool hasLoss() => $_has(3);
  @$pb.TagNumber(4)
  void clearLoss() => clearField(4);

  @$pb.TagNumber(5)
  $core.List<TrainingDimension> get dimensions => $_getList(4);

  @$pb.TagNumber(6)
  $core.String get statusText => $_getSZ(5);
  @$pb.TagNumber(6)
  set statusText($core.String v) { $_setString(5, v); }
  @$pb.TagNumber(6)
  $core.bool hasStatusText() => $_has(5);
  @$pb.TagNumber(6)
  void clearStatusText() => clearField(6);
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
  void clearName() => clearField(1);

  @$pb.TagNumber(2)
  $core.String get description => $_getSZ(1);
  @$pb.TagNumber(2)
  set description($core.String v) { $_setString(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasDescription() => $_has(1);
  @$pb.TagNumber(2)
  void clearDescription() => clearField(2);

  @$pb.TagNumber(3)
  $core.String get version => $_getSZ(2);
  @$pb.TagNumber(3)
  set version($core.String v) { $_setString(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasVersion() => $_has(2);
  @$pb.TagNumber(3)
  void clearVersion() => clearField(3);

  @$pb.TagNumber(4)
  $core.bool get enabled => $_getBF(3);
  @$pb.TagNumber(4)
  set enabled($core.bool v) { $_setBool(3, v); }
  @$pb.TagNumber(4)
  $core.bool hasEnabled() => $_has(3);
  @$pb.TagNumber(4)
  void clearEnabled() => clearField(4);

  @$pb.TagNumber(5)
  $core.String get category => $_getSZ(4);
  @$pb.TagNumber(5)
  set category($core.String v) { $_setString(4, v); }
  @$pb.TagNumber(5)
  $core.bool hasCategory() => $_has(4);
  @$pb.TagNumber(5)
  void clearCategory() => clearField(5);
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
  $core.List<PluginInfo> get plugins => $_getList(0);
}

/// ===== 启动训练请求 / 进度 =====
class TrainingRequest extends $pb.GeneratedMessage {
  factory TrainingRequest({
    $core.int? steps,
  }) {
    final $result = create();
    if (steps != null) {
      $result.steps = steps;
    }
    return $result;
  }
  TrainingRequest._() : super();
  factory TrainingRequest.fromBuffer($core.List<$core.int> i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromBuffer(i, r);
  factory TrainingRequest.fromJson($core.String i, [$pb.ExtensionRegistry r = $pb.ExtensionRegistry.EMPTY]) => create()..mergeFromJson(i, r);

  static final $pb.BuilderInfo _i = $pb.BuilderInfo(_omitMessageNames ? '' : 'TrainingRequest', package: const $pb.PackageName(_omitMessageNames ? '' : 'xiaoling'), createEmptyInstance: create)
    ..a<$core.int>(1, _omitFieldNames ? '' : 'steps', $pb.PbFieldType.O3)
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
  void clearSteps() => clearField(1);
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
  void clearStep() => clearField(1);

  @$pb.TagNumber(2)
  $core.int get totalSteps => $_getIZ(1);
  @$pb.TagNumber(2)
  set totalSteps($core.int v) { $_setSignedInt32(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasTotalSteps() => $_has(1);
  @$pb.TagNumber(2)
  void clearTotalSteps() => clearField(2);

  @$pb.TagNumber(3)
  $core.double get loss => $_getN(2);
  @$pb.TagNumber(3)
  set loss($core.double v) { $_setFloat(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasLoss() => $_has(2);
  @$pb.TagNumber(3)
  void clearLoss() => clearField(3);

  @$pb.TagNumber(4)
  $core.String get status => $_getSZ(3);
  @$pb.TagNumber(4)
  set status($core.String v) { $_setString(3, v); }
  @$pb.TagNumber(4)
  $core.bool hasStatus() => $_has(3);
  @$pb.TagNumber(4)
  void clearStatus() => clearField(4);
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
  void clearVramGb() => clearField(1);

  @$pb.TagNumber(2)
  $core.double get ramGb => $_getN(1);
  @$pb.TagNumber(2)
  set ramGb($core.double v) { $_setDouble(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasRamGb() => $_has(1);
  @$pb.TagNumber(2)
  void clearRamGb() => clearField(2);

  @$pb.TagNumber(3)
  $core.int get cpuCores => $_getIZ(2);
  @$pb.TagNumber(3)
  set cpuCores($core.int v) { $_setSignedInt32(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasCpuCores() => $_has(2);
  @$pb.TagNumber(3)
  void clearCpuCores() => clearField(3);

  @$pb.TagNumber(4)
  $core.double get diskFreeGb => $_getN(3);
  @$pb.TagNumber(4)
  set diskFreeGb($core.double v) { $_setDouble(3, v); }
  @$pb.TagNumber(4)
  $core.bool hasDiskFreeGb() => $_has(3);
  @$pb.TagNumber(4)
  void clearDiskFreeGb() => clearField(4);

  @$pb.TagNumber(5)
  $core.String get gpuName => $_getSZ(4);
  @$pb.TagNumber(5)
  set gpuName($core.String v) { $_setString(4, v); }
  @$pb.TagNumber(5)
  $core.bool hasGpuName() => $_has(4);
  @$pb.TagNumber(5)
  void clearGpuName() => clearField(5);

  @$pb.TagNumber(6)
  $core.String get platform => $_getSZ(5);
  @$pb.TagNumber(6)
  set platform($core.String v) { $_setString(5, v); }
  @$pb.TagNumber(6)
  $core.bool hasPlatform() => $_has(5);
  @$pb.TagNumber(6)
  void clearPlatform() => clearField(6);

  @$pb.TagNumber(7)
  $core.bool get hasCuda => $_getBF(6);
  @$pb.TagNumber(7)
  set hasCuda($core.bool v) { $_setBool(6, v); }
  @$pb.TagNumber(7)
  $core.bool hasHasCuda() => $_has(6);
  @$pb.TagNumber(7)
  void clearHasCuda() => clearField(7);

  @$pb.TagNumber(8)
  $core.bool get hasMetal => $_getBF(7);
  @$pb.TagNumber(8)
  set hasMetal($core.bool v) { $_setBool(7, v); }
  @$pb.TagNumber(8)
  $core.bool hasHasMetal() => $_has(7);
  @$pb.TagNumber(8)
  void clearHasMetal() => clearField(8);
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
  void clearName() => clearField(1);

  @$pb.TagNumber(2)
  $core.String get params => $_getSZ(1);
  @$pb.TagNumber(2)
  set params($core.String v) { $_setString(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasParams() => $_has(1);
  @$pb.TagNumber(2)
  void clearParams() => clearField(2);

  @$pb.TagNumber(3)
  $core.String get quant => $_getSZ(2);
  @$pb.TagNumber(3)
  set quant($core.String v) { $_setString(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasQuant() => $_has(2);
  @$pb.TagNumber(3)
  void clearQuant() => clearField(3);

  @$pb.TagNumber(4)
  $core.double get vramGb => $_getN(3);
  @$pb.TagNumber(4)
  set vramGb($core.double v) { $_setDouble(3, v); }
  @$pb.TagNumber(4)
  $core.bool hasVramGb() => $_has(3);
  @$pb.TagNumber(4)
  void clearVramGb() => clearField(4);

  @$pb.TagNumber(5)
  $core.double get ramGb => $_getN(4);
  @$pb.TagNumber(5)
  set ramGb($core.double v) { $_setDouble(4, v); }
  @$pb.TagNumber(5)
  $core.bool hasRamGb() => $_has(4);
  @$pb.TagNumber(5)
  void clearRamGb() => clearField(5);

  @$pb.TagNumber(6)
  $core.int get quality => $_getIZ(5);
  @$pb.TagNumber(6)
  set quality($core.int v) { $_setSignedInt32(5, v); }
  @$pb.TagNumber(6)
  $core.bool hasQuality() => $_has(5);
  @$pb.TagNumber(6)
  void clearQuality() => clearField(6);

  @$pb.TagNumber(7)
  $core.String get context => $_getSZ(6);
  @$pb.TagNumber(7)
  set context($core.String v) { $_setString(6, v); }
  @$pb.TagNumber(7)
  $core.bool hasContext() => $_has(6);
  @$pb.TagNumber(7)
  void clearContext() => clearField(7);

  @$pb.TagNumber(8)
  $core.double get sizeMb => $_getN(7);
  @$pb.TagNumber(8)
  set sizeMb($core.double v) { $_setDouble(7, v); }
  @$pb.TagNumber(8)
  $core.bool hasSizeMb() => $_has(7);
  @$pb.TagNumber(8)
  void clearSizeMb() => clearField(8);

  @$pb.TagNumber(9)
  $core.bool get canRun => $_getBF(8);
  @$pb.TagNumber(9)
  set canRun($core.bool v) { $_setBool(8, v); }
  @$pb.TagNumber(9)
  $core.bool hasCanRun() => $_has(8);
  @$pb.TagNumber(9)
  void clearCanRun() => clearField(9);

  @$pb.TagNumber(10)
  $core.bool get recommended => $_getBF(9);
  @$pb.TagNumber(10)
  set recommended($core.bool v) { $_setBool(9, v); }
  @$pb.TagNumber(10)
  $core.bool hasRecommended() => $_has(9);
  @$pb.TagNumber(10)
  void clearRecommended() => clearField(10);
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
  $core.List<RecommendedModel> get models => $_getList(0);
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
  void clearModelName() => clearField(1);

  @$pb.TagNumber(2)
  $core.String get quant => $_getSZ(1);
  @$pb.TagNumber(2)
  set quant($core.String v) { $_setString(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasQuant() => $_has(1);
  @$pb.TagNumber(2)
  void clearQuant() => clearField(2);
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
  void clearPercent() => clearField(1);

  @$pb.TagNumber(2)
  $core.double get downloadedMb => $_getN(1);
  @$pb.TagNumber(2)
  set downloadedMb($core.double v) { $_setDouble(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasDownloadedMb() => $_has(1);
  @$pb.TagNumber(2)
  void clearDownloadedMb() => clearField(2);

  @$pb.TagNumber(3)
  $core.double get totalMb => $_getN(2);
  @$pb.TagNumber(3)
  set totalMb($core.double v) { $_setDouble(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasTotalMb() => $_has(2);
  @$pb.TagNumber(3)
  void clearTotalMb() => clearField(3);

  @$pb.TagNumber(4)
  $core.String get status => $_getSZ(3);
  @$pb.TagNumber(4)
  set status($core.String v) { $_setString(3, v); }
  @$pb.TagNumber(4)
  $core.bool hasStatus() => $_has(3);
  @$pb.TagNumber(4)
  void clearStatus() => clearField(4);
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
  void clearName() => clearField(1);
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
  void clearId() => clearField(1);

  @$pb.TagNumber(2)
  $core.String get name => $_getSZ(1);
  @$pb.TagNumber(2)
  set name($core.String v) { $_setString(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasName() => $_has(1);
  @$pb.TagNumber(2)
  void clearName() => clearField(2);

  @$pb.TagNumber(3)
  $core.String get lang => $_getSZ(2);
  @$pb.TagNumber(3)
  set lang($core.String v) { $_setString(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasLang() => $_has(2);
  @$pb.TagNumber(3)
  void clearLang() => clearField(3);
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
  $core.List<VoiceInfo> get voices => $_getList(0);
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
  void clearVoiceId() => clearField(1);
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
  void clearText() => clearField(1);
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
  void clearData() => clearField(1);

  @$pb.TagNumber(2)
  $core.bool get done => $_getBF(1);
  @$pb.TagNumber(2)
  set done($core.bool v) { $_setBool(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasDone() => $_has(1);
  @$pb.TagNumber(2)
  void clearDone() => clearField(2);
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
  void clearModel() => clearField(1);

  @$pb.TagNumber(2)
  $core.String get voice => $_getSZ(1);
  @$pb.TagNumber(2)
  set voice($core.String v) { $_setString(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasVoice() => $_has(1);
  @$pb.TagNumber(2)
  void clearVoice() => clearField(2);

  @$pb.TagNumber(3)
  $core.String get renderBackend => $_getSZ(2);
  @$pb.TagNumber(3)
  set renderBackend($core.String v) { $_setString(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasRenderBackend() => $_has(2);
  @$pb.TagNumber(3)
  void clearRenderBackend() => clearField(3);

  @$pb.TagNumber(4)
  $core.bool get alwaysOnTop => $_getBF(3);
  @$pb.TagNumber(4)
  set alwaysOnTop($core.bool v) { $_setBool(3, v); }
  @$pb.TagNumber(4)
  $core.bool hasAlwaysOnTop() => $_has(3);
  @$pb.TagNumber(4)
  void clearAlwaysOnTop() => clearField(4);

  @$pb.TagNumber(5)
  $core.bool get autoStart => $_getBF(4);
  @$pb.TagNumber(5)
  set autoStart($core.bool v) { $_setBool(4, v); }
  @$pb.TagNumber(5)
  $core.bool hasAutoStart() => $_has(4);
  @$pb.TagNumber(5)
  void clearAutoStart() => clearField(5);

  @$pb.TagNumber(6)
  $core.bool get asrEnabled => $_getBF(5);
  @$pb.TagNumber(6)
  set asrEnabled($core.bool v) { $_setBool(5, v); }
  @$pb.TagNumber(6)
  $core.bool hasAsrEnabled() => $_has(5);
  @$pb.TagNumber(6)
  void clearAsrEnabled() => clearField(6);

  @$pb.TagNumber(7)
  $core.bool get ttsEnabled => $_getBF(6);
  @$pb.TagNumber(7)
  set ttsEnabled($core.bool v) { $_setBool(6, v); }
  @$pb.TagNumber(7)
  $core.bool hasTtsEnabled() => $_has(6);
  @$pb.TagNumber(7)
  void clearTtsEnabled() => clearField(7);

  @$pb.TagNumber(8)
  $core.bool get readAloudMode => $_getBF(7);
  @$pb.TagNumber(8)
  set readAloudMode($core.bool v) { $_setBool(7, v); }
  @$pb.TagNumber(8)
  $core.bool hasReadAloudMode() => $_has(7);
  @$pb.TagNumber(8)
  void clearReadAloudMode() => clearField(8);

  /// 人格预设名（活跃中），对应 config.persona
  @$pb.TagNumber(9)
  $core.String get persona => $_getSZ(8);
  @$pb.TagNumber(9)
  set persona($core.String v) { $_setString(8, v); }
  @$pb.TagNumber(9)
  $core.bool hasPersona() => $_has(8);
  @$pb.TagNumber(9)
  void clearPersona() => clearField(9);

  /// 用户名，对应 config.user_name
  @$pb.TagNumber(10)
  $core.String get userName => $_getSZ(9);
  @$pb.TagNumber(10)
  set userName($core.String v) { $_setString(9, v); }
  @$pb.TagNumber(10)
  $core.bool hasUserName() => $_has(9);
  @$pb.TagNumber(10)
  void clearUserName() => clearField(10);
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
  void clearModel() => clearField(1);

  @$pb.TagNumber(2)
  $core.String get voice => $_getSZ(1);
  @$pb.TagNumber(2)
  set voice($core.String v) { $_setString(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasVoice() => $_has(1);
  @$pb.TagNumber(2)
  void clearVoice() => clearField(2);

  @$pb.TagNumber(3)
  $core.String get renderBackend => $_getSZ(2);
  @$pb.TagNumber(3)
  set renderBackend($core.String v) { $_setString(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasRenderBackend() => $_has(2);
  @$pb.TagNumber(3)
  void clearRenderBackend() => clearField(3);

  @$pb.TagNumber(4)
  $core.bool get alwaysOnTop => $_getBF(3);
  @$pb.TagNumber(4)
  set alwaysOnTop($core.bool v) { $_setBool(3, v); }
  @$pb.TagNumber(4)
  $core.bool hasAlwaysOnTop() => $_has(3);
  @$pb.TagNumber(4)
  void clearAlwaysOnTop() => clearField(4);

  @$pb.TagNumber(5)
  $core.bool get autoStart => $_getBF(4);
  @$pb.TagNumber(5)
  set autoStart($core.bool v) { $_setBool(4, v); }
  @$pb.TagNumber(5)
  $core.bool hasAutoStart() => $_has(4);
  @$pb.TagNumber(5)
  void clearAutoStart() => clearField(5);

  @$pb.TagNumber(6)
  $core.bool get asrEnabled => $_getBF(5);
  @$pb.TagNumber(6)
  set asrEnabled($core.bool v) { $_setBool(5, v); }
  @$pb.TagNumber(6)
  $core.bool hasAsrEnabled() => $_has(5);
  @$pb.TagNumber(6)
  void clearAsrEnabled() => clearField(6);

  @$pb.TagNumber(7)
  $core.bool get ttsEnabled => $_getBF(6);
  @$pb.TagNumber(7)
  set ttsEnabled($core.bool v) { $_setBool(6, v); }
  @$pb.TagNumber(7)
  $core.bool hasTtsEnabled() => $_has(6);
  @$pb.TagNumber(7)
  void clearTtsEnabled() => clearField(7);

  @$pb.TagNumber(8)
  $core.bool get readAloudMode => $_getBF(7);
  @$pb.TagNumber(8)
  set readAloudMode($core.bool v) { $_setBool(7, v); }
  @$pb.TagNumber(8)
  $core.bool hasReadAloudMode() => $_has(7);
  @$pb.TagNumber(8)
  void clearReadAloudMode() => clearField(8);

  @$pb.TagNumber(9)
  $core.String get persona => $_getSZ(8);
  @$pb.TagNumber(9)
  set persona($core.String v) { $_setString(8, v); }
  @$pb.TagNumber(9)
  $core.bool hasPersona() => $_has(8);
  @$pb.TagNumber(9)
  void clearPersona() => clearField(9);

  @$pb.TagNumber(10)
  $core.String get userName => $_getSZ(9);
  @$pb.TagNumber(10)
  set userName($core.String v) { $_setString(9, v); }
  @$pb.TagNumber(10)
  $core.bool hasUserName() => $_has(9);
  @$pb.TagNumber(10)
  void clearUserName() => clearField(10);
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
  void clearEmotion() => clearField(1);

  @$pb.TagNumber(2)
  $core.double get emotionIntensity => $_getN(1);
  @$pb.TagNumber(2)
  set emotionIntensity($core.double v) { $_setDouble(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasEmotionIntensity() => $_has(1);
  @$pb.TagNumber(2)
  void clearEmotionIntensity() => clearField(2);

  @$pb.TagNumber(3)
  $core.String get relationship => $_getSZ(2);
  @$pb.TagNumber(3)
  set relationship($core.String v) { $_setString(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasRelationship() => $_has(2);
  @$pb.TagNumber(3)
  void clearRelationship() => clearField(3);

  @$pb.TagNumber(4)
  $core.double get relationshipScore => $_getN(3);
  @$pb.TagNumber(4)
  set relationshipScore($core.double v) { $_setDouble(3, v); }
  @$pb.TagNumber(4)
  $core.bool hasRelationshipScore() => $_has(3);
  @$pb.TagNumber(4)
  void clearRelationshipScore() => clearField(4);

  @$pb.TagNumber(5)
  $core.double get relationshipProgress => $_getN(4);
  @$pb.TagNumber(5)
  set relationshipProgress($core.double v) { $_setDouble(4, v); }
  @$pb.TagNumber(5)
  $core.bool hasRelationshipProgress() => $_has(4);
  @$pb.TagNumber(5)
  void clearRelationshipProgress() => clearField(5);

  @$pb.TagNumber(6)
  $core.int get remindersPending => $_getIZ(5);
  @$pb.TagNumber(6)
  set remindersPending($core.int v) { $_setSignedInt32(5, v); }
  @$pb.TagNumber(6)
  $core.bool hasRemindersPending() => $_has(5);
  @$pb.TagNumber(6)
  void clearRemindersPending() => clearField(6);

  @$pb.TagNumber(7)
  $core.String get persona => $_getSZ(6);
  @$pb.TagNumber(7)
  set persona($core.String v) { $_setString(6, v); }
  @$pb.TagNumber(7)
  $core.bool hasPersona() => $_has(6);
  @$pb.TagNumber(7)
  void clearPersona() => clearField(7);

  @$pb.TagNumber(8)
  $core.String get userName => $_getSZ(7);
  @$pb.TagNumber(8)
  set userName($core.String v) { $_setString(7, v); }
  @$pb.TagNumber(8)
  $core.bool hasUserName() => $_has(7);
  @$pb.TagNumber(8)
  void clearUserName() => clearField(8);

  /// 五维情绪构成，用于雷达图
  @$pb.TagNumber(9)
  $core.List<PersonaAxis> get axes => $_getList(8);
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
  void clearName() => clearField(1);

  @$pb.TagNumber(2)
  $core.String get label => $_getSZ(1);
  @$pb.TagNumber(2)
  set label($core.String v) { $_setString(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasLabel() => $_has(1);
  @$pb.TagNumber(2)
  void clearLabel() => clearField(2);

  @$pb.TagNumber(3)
  $core.double get value => $_getN(2);
  @$pb.TagNumber(3)
  set value($core.double v) { $_setDouble(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasValue() => $_has(2);
  @$pb.TagNumber(3)
  void clearValue() => clearField(3);
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
  void clearId() => clearField(1);

  @$pb.TagNumber(2)
  $core.String get name => $_getSZ(1);
  @$pb.TagNumber(2)
  set name($core.String v) { $_setString(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasName() => $_has(1);
  @$pb.TagNumber(2)
  void clearName() => clearField(2);

  @$pb.TagNumber(3)
  $core.String get description => $_getSZ(2);
  @$pb.TagNumber(3)
  set description($core.String v) { $_setString(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasDescription() => $_has(2);
  @$pb.TagNumber(3)
  void clearDescription() => clearField(3);

  @$pb.TagNumber(4)
  $core.String get promptHint => $_getSZ(3);
  @$pb.TagNumber(4)
  set promptHint($core.String v) { $_setString(3, v); }
  @$pb.TagNumber(4)
  $core.bool hasPromptHint() => $_has(3);
  @$pb.TagNumber(4)
  void clearPromptHint() => clearField(4);

  @$pb.TagNumber(5)
  $core.bool get builtin => $_getBF(4);
  @$pb.TagNumber(5)
  set builtin($core.bool v) { $_setBool(4, v); }
  @$pb.TagNumber(5)
  $core.bool hasBuiltin() => $_has(4);
  @$pb.TagNumber(5)
  void clearBuiltin() => clearField(5);

  @$pb.TagNumber(6)
  $core.bool get active => $_getBF(5);
  @$pb.TagNumber(6)
  set active($core.bool v) { $_setBool(5, v); }
  @$pb.TagNumber(6)
  $core.bool hasActive() => $_has(5);
  @$pb.TagNumber(6)
  void clearActive() => clearField(6);
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
  $core.List<PersonaPreset> get presets => $_getList(0);
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
  void clearId() => clearField(1);

  @$pb.TagNumber(2)
  $core.String get name => $_getSZ(1);
  @$pb.TagNumber(2)
  set name($core.String v) { $_setString(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasName() => $_has(1);
  @$pb.TagNumber(2)
  void clearName() => clearField(2);

  @$pb.TagNumber(3)
  $core.String get description => $_getSZ(2);
  @$pb.TagNumber(3)
  set description($core.String v) { $_setString(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasDescription() => $_has(2);
  @$pb.TagNumber(3)
  void clearDescription() => clearField(3);

  @$pb.TagNumber(4)
  $core.String get promptHint => $_getSZ(3);
  @$pb.TagNumber(4)
  set promptHint($core.String v) { $_setString(3, v); }
  @$pb.TagNumber(4)
  $core.bool hasPromptHint() => $_has(3);
  @$pb.TagNumber(4)
  void clearPromptHint() => clearField(4);
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
  void clearText() => clearField(1);

  @$pb.TagNumber(2)
  $core.double get dueAt => $_getN(1);
  @$pb.TagNumber(2)
  set dueAt($core.double v) { $_setDouble(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasDueAt() => $_has(1);
  @$pb.TagNumber(2)
  void clearDueAt() => clearField(2);

  @$pb.TagNumber(3)
  $core.bool get done => $_getBF(2);
  @$pb.TagNumber(3)
  set done($core.bool v) { $_setBool(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasDone() => $_has(2);
  @$pb.TagNumber(3)
  void clearDone() => clearField(3);

  @$pb.TagNumber(4)
  $core.double get createdAt => $_getN(3);
  @$pb.TagNumber(4)
  set createdAt($core.double v) { $_setDouble(3, v); }
  @$pb.TagNumber(4)
  $core.bool hasCreatedAt() => $_has(3);
  @$pb.TagNumber(4)
  void clearCreatedAt() => clearField(4);

  @$pb.TagNumber(5)
  $fixnum.Int64 get secondsLeft => $_getI64(4);
  @$pb.TagNumber(5)
  set secondsLeft($fixnum.Int64 v) { $_setInt64(4, v); }
  @$pb.TagNumber(5)
  $core.bool hasSecondsLeft() => $_has(4);
  @$pb.TagNumber(5)
  void clearSecondsLeft() => clearField(5);
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
  $core.List<ReminderItem> get items => $_getList(0);

  @$pb.TagNumber(2)
  $core.int get unread => $_getIZ(1);
  @$pb.TagNumber(2)
  set unread($core.int v) { $_setSignedInt32(1, v); }
  @$pb.TagNumber(2)
  $core.bool hasUnread() => $_has(1);
  @$pb.TagNumber(2)
  void clearUnread() => clearField(2);

  @$pb.TagNumber(3)
  $core.int get pending => $_getIZ(2);
  @$pb.TagNumber(3)
  set pending($core.int v) { $_setSignedInt32(2, v); }
  @$pb.TagNumber(3)
  $core.bool hasPending() => $_has(2);
  @$pb.TagNumber(3)
  void clearPending() => clearField(3);
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
  void clearDueAt() => clearField(1);
}


const _omitFieldNames = $core.bool.fromEnvironment('protobuf.omit_field_names');
const _omitMessageNames = $core.bool.fromEnvironment('protobuf.omit_message_names');
