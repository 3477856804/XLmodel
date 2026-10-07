//
//  Generated code. Do not modify.
//  source: xiaoling.proto
//
// @dart = 2.12

// ignore_for_file: annotate_overrides, camel_case_types, comment_references
// ignore_for_file: constant_identifier_names, library_prefixes
// ignore_for_file: non_constant_identifier_names, prefer_final_fields
// ignore_for_file: unnecessary_import, unnecessary_this, unused_import

import 'dart:convert' as $convert;
import 'dart:core' as $core;
import 'dart:typed_data' as $typed_data;

@$core.Deprecated('Use emptyDescriptor instead')
const Empty$json = {
  '1': 'Empty',
};

/// Descriptor for `Empty`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List emptyDescriptor = $convert.base64Decode(
    'CgVFbXB0eQ==');

@$core.Deprecated('Use chatRequestDescriptor instead')
const ChatRequest$json = {
  '1': 'ChatRequest',
  '2': [
    {'1': 'text', '3': 1, '4': 1, '5': 9, '10': 'text'},
  ],
};

/// Descriptor for `ChatRequest`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List chatRequestDescriptor = $convert.base64Decode(
    'CgtDaGF0UmVxdWVzdBISCgR0ZXh0GAEgASgJUgR0ZXh0');

@$core.Deprecated('Use chatChunkDescriptor instead')
const ChatChunk$json = {
  '1': 'ChatChunk',
  '2': [
    {'1': 'delta', '3': 1, '4': 1, '5': 9, '10': 'delta'},
    {'1': 'done', '3': 2, '4': 1, '5': 8, '10': 'done'},
    {'1': 'error', '3': 3, '4': 1, '5': 9, '10': 'error'},
  ],
};

/// Descriptor for `ChatChunk`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List chatChunkDescriptor = $convert.base64Decode(
    'CglDaGF0Q2h1bmsSFAoFZGVsdGEYASABKAlSBWRlbHRhEhIKBGRvbmUYAiABKAhSBGRvbmUSFA'
    'oFZXJyb3IYAyABKAlSBWVycm9y');

@$core.Deprecated('Use statusRequestDescriptor instead')
const StatusRequest$json = {
  '1': 'StatusRequest',
};

/// Descriptor for `StatusRequest`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List statusRequestDescriptor = $convert.base64Decode(
    'Cg1TdGF0dXNSZXF1ZXN0');

@$core.Deprecated('Use statusReplyDescriptor instead')
const StatusReply$json = {
  '1': 'StatusReply',
  '2': [
    {'1': 'ok', '3': 1, '4': 1, '5': 8, '10': 'ok'},
    {'1': 'message', '3': 2, '4': 1, '5': 9, '10': 'message'},
    {'1': 'stage', '3': 3, '4': 1, '5': 9, '10': 'stage'},
    {'1': 'model', '3': 4, '4': 1, '5': 9, '10': 'model'},
    {'1': 'backend', '3': 5, '4': 1, '5': 9, '10': 'backend'},
    {'1': 'progress', '3': 6, '4': 1, '5': 1, '10': 'progress'},
    {'1': 'version', '3': 7, '4': 1, '5': 9, '10': 'version'},
  ],
};

/// Descriptor for `StatusReply`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List statusReplyDescriptor = $convert.base64Decode(
    'CgtTdGF0dXNSZXBseRIOCgJvaxgBIAEoCFICb2sSGAoHbWVzc2FnZRgCIAEoCVIHbWVzc2FnZR'
    'IUCgVzdGFnZRgDIAEoCVIFc3RhZ2USFAoFbW9kZWwYBCABKAlSBW1vZGVsEhgKB2JhY2tlbmQY'
    'BSABKAlSB2JhY2tlbmQSGgoIcHJvZ3Jlc3MYBiABKAFSCHByb2dyZXNzEhgKB3ZlcnNpb24YBy'
    'ABKAlSB3ZlcnNpb24=');

@$core.Deprecated('Use listRequestDescriptor instead')
const ListRequest$json = {
  '1': 'ListRequest',
};

/// Descriptor for `ListRequest`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List listRequestDescriptor = $convert.base64Decode(
    'CgtMaXN0UmVxdWVzdA==');

@$core.Deprecated('Use modelInfoDescriptor instead')
const ModelInfo$json = {
  '1': 'ModelInfo',
  '2': [
    {'1': 'name', '3': 1, '4': 1, '5': 9, '10': 'name'},
    {'1': 'path', '3': 2, '4': 1, '5': 9, '10': 'path'},
    {'1': 'size_mb', '3': 3, '4': 1, '5': 1, '10': 'sizeMb'},
  ],
};

/// Descriptor for `ModelInfo`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List modelInfoDescriptor = $convert.base64Decode(
    'CglNb2RlbEluZm8SEgoEbmFtZRgBIAEoCVIEbmFtZRISCgRwYXRoGAIgASgJUgRwYXRoEhcKB3'
    'NpemVfbWIYAyABKAFSBnNpemVNYg==');

@$core.Deprecated('Use modelListDescriptor instead')
const ModelList$json = {
  '1': 'ModelList',
  '2': [
    {'1': 'models', '3': 1, '4': 3, '5': 11, '6': '.xiaoling.ModelInfo', '10': 'models'},
  ],
};

/// Descriptor for `ModelList`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List modelListDescriptor = $convert.base64Decode(
    'CglNb2RlbExpc3QSKwoGbW9kZWxzGAEgAygLMhMueGlhb2xpbmcuTW9kZWxJbmZvUgZtb2RlbH'
    'M=');

@$core.Deprecated('Use switchModelRequestDescriptor instead')
const SwitchModelRequest$json = {
  '1': 'SwitchModelRequest',
  '2': [
    {'1': 'path', '3': 1, '4': 1, '5': 9, '10': 'path'},
  ],
};

/// Descriptor for `SwitchModelRequest`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List switchModelRequestDescriptor = $convert.base64Decode(
    'ChJTd2l0Y2hNb2RlbFJlcXVlc3QSEgoEcGF0aBgBIAEoCVIEcGF0aA==');

@$core.Deprecated('Use commandRequestDescriptor instead')
const CommandRequest$json = {
  '1': 'CommandRequest',
  '2': [
    {'1': 'command', '3': 1, '4': 1, '5': 9, '10': 'command'},
  ],
};

/// Descriptor for `CommandRequest`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List commandRequestDescriptor = $convert.base64Decode(
    'Cg5Db21tYW5kUmVxdWVzdBIYCgdjb21tYW5kGAEgASgJUgdjb21tYW5k');

@$core.Deprecated('Use commandReplyDescriptor instead')
const CommandReply$json = {
  '1': 'CommandReply',
  '2': [
    {'1': 'output', '3': 1, '4': 1, '5': 9, '10': 'output'},
  ],
};

/// Descriptor for `CommandReply`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List commandReplyDescriptor = $convert.base64Decode(
    'CgxDb21tYW5kUmVwbHkSFgoGb3V0cHV0GAEgASgJUgZvdXRwdXQ=');

@$core.Deprecated('Use actionInfoDescriptor instead')
const ActionInfo$json = {
  '1': 'ActionInfo',
  '2': [
    {'1': 'name', '3': 1, '4': 1, '5': 9, '10': 'name'},
    {'1': 'path', '3': 2, '4': 1, '5': 9, '10': 'path'},
    {'1': 'dance', '3': 3, '4': 1, '5': 8, '10': 'dance'},
    {'1': 'idle', '3': 4, '4': 1, '5': 8, '10': 'idle'},
  ],
};

/// Descriptor for `ActionInfo`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List actionInfoDescriptor = $convert.base64Decode(
    'CgpBY3Rpb25JbmZvEhIKBG5hbWUYASABKAlSBG5hbWUSEgoEcGF0aBgCIAEoCVIEcGF0aBIUCg'
    'VkYW5jZRgDIAEoCFIFZGFuY2USEgoEaWRsZRgEIAEoCFIEaWRsZQ==');

@$core.Deprecated('Use actionListDescriptor instead')
const ActionList$json = {
  '1': 'ActionList',
  '2': [
    {'1': 'actions', '3': 1, '4': 3, '5': 11, '6': '.xiaoling.ActionInfo', '10': 'actions'},
  ],
};

/// Descriptor for `ActionList`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List actionListDescriptor = $convert.base64Decode(
    'CgpBY3Rpb25MaXN0Ei4KB2FjdGlvbnMYASADKAsyFC54aWFvbGluZy5BY3Rpb25JbmZvUgdhY3'
    'Rpb25z');

@$core.Deprecated('Use playActionRequestDescriptor instead')
const PlayActionRequest$json = {
  '1': 'PlayActionRequest',
  '2': [
    {'1': 'path', '3': 1, '4': 1, '5': 9, '10': 'path'},
  ],
};

/// Descriptor for `PlayActionRequest`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List playActionRequestDescriptor = $convert.base64Decode(
    'ChFQbGF5QWN0aW9uUmVxdWVzdBISCgRwYXRoGAEgASgJUgRwYXRo');

@$core.Deprecated('Use shutdownRequestDescriptor instead')
const ShutdownRequest$json = {
  '1': 'ShutdownRequest',
};

/// Descriptor for `ShutdownRequest`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List shutdownRequestDescriptor = $convert.base64Decode(
    'Cg9TaHV0ZG93blJlcXVlc3Q=');

@$core.Deprecated('Use growthStatusReplyDescriptor instead')
const GrowthStatusReply$json = {
  '1': 'GrowthStatusReply',
  '2': [
    {'1': 'stage', '3': 1, '4': 1, '5': 9, '10': 'stage'},
    {'1': 'progress_percent', '3': 2, '4': 1, '5': 1, '10': 'progressPercent'},
    {'1': 'total_interactions', '3': 3, '4': 1, '5': 5, '10': 'totalInteractions'},
    {'1': 'current_generation', '3': 4, '4': 1, '5': 5, '10': 'currentGeneration'},
    {'1': 'total_generations', '3': 5, '4': 1, '5': 5, '10': 'totalGenerations'},
    {'1': 'current_rank', '3': 6, '4': 1, '5': 9, '10': 'currentRank'},
    {'1': 'emotion', '3': 7, '4': 1, '5': 9, '10': 'emotion'},
    {'1': 'training_paused', '3': 8, '4': 1, '5': 8, '10': 'trainingPaused'},
    {'1': 'status_text', '3': 9, '4': 1, '5': 9, '10': 'statusText'},
  ],
};

/// Descriptor for `GrowthStatusReply`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List growthStatusReplyDescriptor = $convert.base64Decode(
    'ChFHcm93dGhTdGF0dXNSZXBseRIUCgVzdGFnZRgBIAEoCVIFc3RhZ2USKQoQcHJvZ3Jlc3NfcG'
    'VyY2VudBgCIAEoAVIPcHJvZ3Jlc3NQZXJjZW50Ei0KEnRvdGFsX2ludGVyYWN0aW9ucxgDIAEo'
    'BVIRdG90YWxJbnRlcmFjdGlvbnMSLQoSY3VycmVudF9nZW5lcmF0aW9uGAQgASgFUhFjdXJyZW'
    '50R2VuZXJhdGlvbhIrChF0b3RhbF9nZW5lcmF0aW9ucxgFIAEoBVIQdG90YWxHZW5lcmF0aW9u'
    'cxIhCgxjdXJyZW50X3JhbmsYBiABKAlSC2N1cnJlbnRSYW5rEhgKB2Vtb3Rpb24YByABKAlSB2'
    'Vtb3Rpb24SJwoPdHJhaW5pbmdfcGF1c2VkGAggASgIUg50cmFpbmluZ1BhdXNlZBIfCgtzdGF0'
    'dXNfdGV4dBgJIAEoCVIKc3RhdHVzVGV4dA==');

@$core.Deprecated('Use trainingDimensionDescriptor instead')
const TrainingDimension$json = {
  '1': 'TrainingDimension',
  '2': [
    {'1': 'name', '3': 1, '4': 1, '5': 9, '10': 'name'},
    {'1': 'value', '3': 2, '4': 1, '5': 1, '10': 'value'},
    {'1': 'label', '3': 3, '4': 1, '5': 9, '10': 'label'},
  ],
};

/// Descriptor for `TrainingDimension`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List trainingDimensionDescriptor = $convert.base64Decode(
    'ChFUcmFpbmluZ0RpbWVuc2lvbhISCgRuYW1lGAEgASgJUgRuYW1lEhQKBXZhbHVlGAIgASgBUg'
    'V2YWx1ZRIUCgVsYWJlbBgDIAEoCVIFbGFiZWw=');

@$core.Deprecated('Use trainingStatusReplyDescriptor instead')
const TrainingStatusReply$json = {
  '1': 'TrainingStatusReply',
  '2': [
    {'1': 'is_training', '3': 1, '4': 1, '5': 8, '10': 'isTraining'},
    {'1': 'current_epoch', '3': 2, '4': 1, '5': 5, '10': 'currentEpoch'},
    {'1': 'total_epochs', '3': 3, '4': 1, '5': 5, '10': 'totalEpochs'},
    {'1': 'loss', '3': 4, '4': 1, '5': 1, '10': 'loss'},
    {'1': 'dimensions', '3': 5, '4': 3, '5': 11, '6': '.xiaoling.TrainingDimension', '10': 'dimensions'},
    {'1': 'status_text', '3': 6, '4': 1, '5': 9, '10': 'statusText'},
  ],
};

/// Descriptor for `TrainingStatusReply`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List trainingStatusReplyDescriptor = $convert.base64Decode(
    'ChNUcmFpbmluZ1N0YXR1c1JlcGx5Eh8KC2lzX3RyYWluaW5nGAEgASgIUgppc1RyYWluaW5nEi'
    'MKDWN1cnJlbnRfZXBvY2gYAiABKAVSDGN1cnJlbnRFcG9jaBIhCgx0b3RhbF9lcG9jaHMYAyAB'
    'KAVSC3RvdGFsRXBvY2hzEhIKBGxvc3MYBCABKAFSBGxvc3MSOwoKZGltZW5zaW9ucxgFIAMoCz'
    'IbLnhpYW9saW5nLlRyYWluaW5nRGltZW5zaW9uUgpkaW1lbnNpb25zEh8KC3N0YXR1c190ZXh0'
    'GAYgASgJUgpzdGF0dXNUZXh0');

@$core.Deprecated('Use pluginInfoDescriptor instead')
const PluginInfo$json = {
  '1': 'PluginInfo',
  '2': [
    {'1': 'name', '3': 1, '4': 1, '5': 9, '10': 'name'},
    {'1': 'description', '3': 2, '4': 1, '5': 9, '10': 'description'},
    {'1': 'version', '3': 3, '4': 1, '5': 9, '10': 'version'},
    {'1': 'enabled', '3': 4, '4': 1, '5': 8, '10': 'enabled'},
    {'1': 'category', '3': 5, '4': 1, '5': 9, '10': 'category'},
  ],
};

/// Descriptor for `PluginInfo`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List pluginInfoDescriptor = $convert.base64Decode(
    'CgpQbHVnaW5JbmZvEhIKBG5hbWUYASABKAlSBG5hbWUSIAoLZGVzY3JpcHRpb24YAiABKAlSC2'
    'Rlc2NyaXB0aW9uEhgKB3ZlcnNpb24YAyABKAlSB3ZlcnNpb24SGAoHZW5hYmxlZBgEIAEoCFIH'
    'ZW5hYmxlZBIaCghjYXRlZ29yeRgFIAEoCVIIY2F0ZWdvcnk=');

@$core.Deprecated('Use pluginListDescriptor instead')
const PluginList$json = {
  '1': 'PluginList',
  '2': [
    {'1': 'plugins', '3': 1, '4': 3, '5': 11, '6': '.xiaoling.PluginInfo', '10': 'plugins'},
  ],
};

/// Descriptor for `PluginList`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List pluginListDescriptor = $convert.base64Decode(
    'CgpQbHVnaW5MaXN0Ei4KB3BsdWdpbnMYASADKAsyFC54aWFvbGluZy5QbHVnaW5JbmZvUgdwbH'
    'VnaW5z');

@$core.Deprecated('Use trainingRequestDescriptor instead')
const TrainingRequest$json = {
  '1': 'TrainingRequest',
  '2': [
    {'1': 'steps', '3': 1, '4': 1, '5': 5, '10': 'steps'},
  ],
};

/// Descriptor for `TrainingRequest`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List trainingRequestDescriptor = $convert.base64Decode(
    'Cg9UcmFpbmluZ1JlcXVlc3QSFAoFc3RlcHMYASABKAVSBXN0ZXBz');

@$core.Deprecated('Use trainingProgressDescriptor instead')
const TrainingProgress$json = {
  '1': 'TrainingProgress',
  '2': [
    {'1': 'step', '3': 1, '4': 1, '5': 5, '10': 'step'},
    {'1': 'total_steps', '3': 2, '4': 1, '5': 5, '10': 'totalSteps'},
    {'1': 'loss', '3': 3, '4': 1, '5': 2, '10': 'loss'},
    {'1': 'status', '3': 4, '4': 1, '5': 9, '10': 'status'},
  ],
};

/// Descriptor for `TrainingProgress`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List trainingProgressDescriptor = $convert.base64Decode(
    'ChBUcmFpbmluZ1Byb2dyZXNzEhIKBHN0ZXAYASABKAVSBHN0ZXASHwoLdG90YWxfc3RlcHMYAi'
    'ABKAVSCnRvdGFsU3RlcHMSEgoEbG9zcxgDIAEoAlIEbG9zcxIWCgZzdGF0dXMYBCABKAlSBnN0'
    'YXR1cw==');

@$core.Deprecated('Use hardwareInfoDescriptor instead')
const HardwareInfo$json = {
  '1': 'HardwareInfo',
  '2': [
    {'1': 'vram_gb', '3': 1, '4': 1, '5': 1, '10': 'vramGb'},
    {'1': 'ram_gb', '3': 2, '4': 1, '5': 1, '10': 'ramGb'},
    {'1': 'cpu_cores', '3': 3, '4': 1, '5': 5, '10': 'cpuCores'},
    {'1': 'disk_free_gb', '3': 4, '4': 1, '5': 1, '10': 'diskFreeGb'},
    {'1': 'gpu_name', '3': 5, '4': 1, '5': 9, '10': 'gpuName'},
    {'1': 'platform', '3': 6, '4': 1, '5': 9, '10': 'platform'},
    {'1': 'has_cuda', '3': 7, '4': 1, '5': 8, '10': 'hasCuda'},
    {'1': 'has_metal', '3': 8, '4': 1, '5': 8, '10': 'hasMetal'},
  ],
};

/// Descriptor for `HardwareInfo`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List hardwareInfoDescriptor = $convert.base64Decode(
    'CgxIYXJkd2FyZUluZm8SFwoHdnJhbV9nYhgBIAEoAVIGdnJhbUdiEhUKBnJhbV9nYhgCIAEoAV'
    'IFcmFtR2ISGwoJY3B1X2NvcmVzGAMgASgFUghjcHVDb3JlcxIgCgxkaXNrX2ZyZWVfZ2IYBCAB'
    'KAFSCmRpc2tGcmVlR2ISGQoIZ3B1X25hbWUYBSABKAlSB2dwdU5hbWUSGgoIcGxhdGZvcm0YBi'
    'ABKAlSCHBsYXRmb3JtEhkKCGhhc19jdWRhGAcgASgIUgdoYXNDdWRhEhsKCWhhc19tZXRhbBgI'
    'IAEoCFIIaGFzTWV0YWw=');

@$core.Deprecated('Use hardwareRequestDescriptor instead')
const HardwareRequest$json = {
  '1': 'HardwareRequest',
};

/// Descriptor for `HardwareRequest`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List hardwareRequestDescriptor = $convert.base64Decode(
    'Cg9IYXJkd2FyZVJlcXVlc3Q=');

@$core.Deprecated('Use recommendedModelDescriptor instead')
const RecommendedModel$json = {
  '1': 'RecommendedModel',
  '2': [
    {'1': 'name', '3': 1, '4': 1, '5': 9, '10': 'name'},
    {'1': 'params', '3': 2, '4': 1, '5': 9, '10': 'params'},
    {'1': 'quant', '3': 3, '4': 1, '5': 9, '10': 'quant'},
    {'1': 'vram_gb', '3': 4, '4': 1, '5': 1, '10': 'vramGb'},
    {'1': 'ram_gb', '3': 5, '4': 1, '5': 1, '10': 'ramGb'},
    {'1': 'quality', '3': 6, '4': 1, '5': 5, '10': 'quality'},
    {'1': 'context', '3': 7, '4': 1, '5': 9, '10': 'context'},
    {'1': 'size_mb', '3': 8, '4': 1, '5': 1, '10': 'sizeMb'},
    {'1': 'can_run', '3': 9, '4': 1, '5': 8, '10': 'canRun'},
    {'1': 'recommended', '3': 10, '4': 1, '5': 8, '10': 'recommended'},
  ],
};

/// Descriptor for `RecommendedModel`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List recommendedModelDescriptor = $convert.base64Decode(
    'ChBSZWNvbW1lbmRlZE1vZGVsEhIKBG5hbWUYASABKAlSBG5hbWUSFgoGcGFyYW1zGAIgASgJUg'
    'ZwYXJhbXMSFAoFcXVhbnQYAyABKAlSBXF1YW50EhcKB3ZyYW1fZ2IYBCABKAFSBnZyYW1HYhIV'
    'CgZyYW1fZ2IYBSABKAFSBXJhbUdiEhgKB3F1YWxpdHkYBiABKAVSB3F1YWxpdHkSGAoHY29udG'
    'V4dBgHIAEoCVIHY29udGV4dBIXCgdzaXplX21iGAggASgBUgZzaXplTWISFwoHY2FuX3J1bhgJ'
    'IAEoCFIGY2FuUnVuEiAKC3JlY29tbWVuZGVkGAogASgIUgtyZWNvbW1lbmRlZA==');

@$core.Deprecated('Use recommendedModelListDescriptor instead')
const RecommendedModelList$json = {
  '1': 'RecommendedModelList',
  '2': [
    {'1': 'models', '3': 1, '4': 3, '5': 11, '6': '.xiaoling.RecommendedModel', '10': 'models'},
  ],
};

/// Descriptor for `RecommendedModelList`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List recommendedModelListDescriptor = $convert.base64Decode(
    'ChRSZWNvbW1lbmRlZE1vZGVsTGlzdBIyCgZtb2RlbHMYASADKAsyGi54aWFvbGluZy5SZWNvbW'
    '1lbmRlZE1vZGVsUgZtb2RlbHM=');

@$core.Deprecated('Use downloadRequestDescriptor instead')
const DownloadRequest$json = {
  '1': 'DownloadRequest',
  '2': [
    {'1': 'model_name', '3': 1, '4': 1, '5': 9, '10': 'modelName'},
    {'1': 'quant', '3': 2, '4': 1, '5': 9, '10': 'quant'},
  ],
};

/// Descriptor for `DownloadRequest`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List downloadRequestDescriptor = $convert.base64Decode(
    'Cg9Eb3dubG9hZFJlcXVlc3QSHQoKbW9kZWxfbmFtZRgBIAEoCVIJbW9kZWxOYW1lEhQKBXF1YW'
    '50GAIgASgJUgVxdWFudA==');

@$core.Deprecated('Use downloadProgressDescriptor instead')
const DownloadProgress$json = {
  '1': 'DownloadProgress',
  '2': [
    {'1': 'percent', '3': 1, '4': 1, '5': 1, '10': 'percent'},
    {'1': 'downloaded_mb', '3': 2, '4': 1, '5': 1, '10': 'downloadedMb'},
    {'1': 'total_mb', '3': 3, '4': 1, '5': 1, '10': 'totalMb'},
    {'1': 'status', '3': 4, '4': 1, '5': 9, '10': 'status'},
  ],
};

/// Descriptor for `DownloadProgress`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List downloadProgressDescriptor = $convert.base64Decode(
    'ChBEb3dubG9hZFByb2dyZXNzEhgKB3BlcmNlbnQYASABKAFSB3BlcmNlbnQSIwoNZG93bmxvYW'
    'RlZF9tYhgCIAEoAVIMZG93bmxvYWRlZE1iEhkKCHRvdGFsX21iGAMgASgBUgd0b3RhbE1iEhYK'
    'BnN0YXR1cxgEIAEoCVIGc3RhdHVz');

@$core.Deprecated('Use modelNameRequestDescriptor instead')
const ModelNameRequest$json = {
  '1': 'ModelNameRequest',
  '2': [
    {'1': 'name', '3': 1, '4': 1, '5': 9, '10': 'name'},
  ],
};

/// Descriptor for `ModelNameRequest`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List modelNameRequestDescriptor = $convert.base64Decode(
    'ChBNb2RlbE5hbWVSZXF1ZXN0EhIKBG5hbWUYASABKAlSBG5hbWU=');

@$core.Deprecated('Use voiceInfoDescriptor instead')
const VoiceInfo$json = {
  '1': 'VoiceInfo',
  '2': [
    {'1': 'id', '3': 1, '4': 1, '5': 9, '10': 'id'},
    {'1': 'name', '3': 2, '4': 1, '5': 9, '10': 'name'},
    {'1': 'lang', '3': 3, '4': 1, '5': 9, '10': 'lang'},
  ],
};

/// Descriptor for `VoiceInfo`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List voiceInfoDescriptor = $convert.base64Decode(
    'CglWb2ljZUluZm8SDgoCaWQYASABKAlSAmlkEhIKBG5hbWUYAiABKAlSBG5hbWUSEgoEbGFuZx'
    'gDIAEoCVIEbGFuZw==');

@$core.Deprecated('Use voiceListDescriptor instead')
const VoiceList$json = {
  '1': 'VoiceList',
  '2': [
    {'1': 'voices', '3': 1, '4': 3, '5': 11, '6': '.xiaoling.VoiceInfo', '10': 'voices'},
  ],
};

/// Descriptor for `VoiceList`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List voiceListDescriptor = $convert.base64Decode(
    'CglWb2ljZUxpc3QSKwoGdm9pY2VzGAEgAygLMhMueGlhb2xpbmcuVm9pY2VJbmZvUgZ2b2ljZX'
    'M=');

@$core.Deprecated('Use voiceRequestDescriptor instead')
const VoiceRequest$json = {
  '1': 'VoiceRequest',
  '2': [
    {'1': 'voice_id', '3': 1, '4': 1, '5': 9, '10': 'voiceId'},
  ],
};

/// Descriptor for `VoiceRequest`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List voiceRequestDescriptor = $convert.base64Decode(
    'CgxWb2ljZVJlcXVlc3QSGQoIdm9pY2VfaWQYASABKAlSB3ZvaWNlSWQ=');

@$core.Deprecated('Use readRequestDescriptor instead')
const ReadRequest$json = {
  '1': 'ReadRequest',
  '2': [
    {'1': 'text', '3': 1, '4': 1, '5': 9, '10': 'text'},
  ],
};

/// Descriptor for `ReadRequest`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List readRequestDescriptor = $convert.base64Decode(
    'CgtSZWFkUmVxdWVzdBISCgR0ZXh0GAEgASgJUgR0ZXh0');

@$core.Deprecated('Use audioChunkDescriptor instead')
const AudioChunk$json = {
  '1': 'AudioChunk',
  '2': [
    {'1': 'data', '3': 1, '4': 1, '5': 12, '10': 'data'},
    {'1': 'done', '3': 2, '4': 1, '5': 8, '10': 'done'},
  ],
};

/// Descriptor for `AudioChunk`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List audioChunkDescriptor = $convert.base64Decode(
    'CgpBdWRpb0NodW5rEhIKBGRhdGEYASABKAxSBGRhdGESEgoEZG9uZRgCIAEoCFIEZG9uZQ==');

@$core.Deprecated('Use settingsReplyDescriptor instead')
const SettingsReply$json = {
  '1': 'SettingsReply',
  '2': [
    {'1': 'model', '3': 1, '4': 1, '5': 9, '10': 'model'},
    {'1': 'voice', '3': 2, '4': 1, '5': 9, '10': 'voice'},
    {'1': 'render_backend', '3': 3, '4': 1, '5': 9, '10': 'renderBackend'},
    {'1': 'always_on_top', '3': 4, '4': 1, '5': 8, '10': 'alwaysOnTop'},
    {'1': 'auto_start', '3': 5, '4': 1, '5': 8, '10': 'autoStart'},
    {'1': 'asr_enabled', '3': 6, '4': 1, '5': 8, '10': 'asrEnabled'},
    {'1': 'tts_enabled', '3': 7, '4': 1, '5': 8, '10': 'ttsEnabled'},
    {'1': 'read_aloud_mode', '3': 8, '4': 1, '5': 8, '10': 'readAloudMode'},
    {'1': 'persona', '3': 9, '4': 1, '5': 9, '10': 'persona'},
    {'1': 'user_name', '3': 10, '4': 1, '5': 9, '10': 'userName'},
  ],
};

/// Descriptor for `SettingsReply`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List settingsReplyDescriptor = $convert.base64Decode(
    'Cg1TZXR0aW5nc1JlcGx5EhQKBW1vZGVsGAEgASgJUgVtb2RlbBIUCgV2b2ljZRgCIAEoCVIFdm'
    '9pY2USJQoOcmVuZGVyX2JhY2tlbmQYAyABKAlSDXJlbmRlckJhY2tlbmQSIgoNYWx3YXlzX29u'
    'X3RvcBgEIAEoCFILYWx3YXlzT25Ub3ASHQoKYXV0b19zdGFydBgFIAEoCFIJYXV0b1N0YXJ0Eh'
    '8KC2Fzcl9lbmFibGVkGAYgASgIUgphc3JFbmFibGVkEh8KC3R0c19lbmFibGVkGAcgASgIUgp0'
    'dHNFbmFibGVkEiYKD3JlYWRfYWxvdWRfbW9kZRgIIAEoCFINcmVhZEFsb3VkTW9kZRIYCgdwZX'
    'Jzb25hGAkgASgJUgdwZXJzb25hEhsKCXVzZXJfbmFtZRgKIAEoCVIIdXNlck5hbWU=');

@$core.Deprecated('Use settingsRequestDescriptor instead')
const SettingsRequest$json = {
  '1': 'SettingsRequest',
  '2': [
    {'1': 'model', '3': 1, '4': 1, '5': 9, '9': 0, '10': 'model', '17': true},
    {'1': 'voice', '3': 2, '4': 1, '5': 9, '9': 1, '10': 'voice', '17': true},
    {'1': 'render_backend', '3': 3, '4': 1, '5': 9, '9': 2, '10': 'renderBackend', '17': true},
    {'1': 'always_on_top', '3': 4, '4': 1, '5': 8, '9': 3, '10': 'alwaysOnTop', '17': true},
    {'1': 'auto_start', '3': 5, '4': 1, '5': 8, '9': 4, '10': 'autoStart', '17': true},
    {'1': 'asr_enabled', '3': 6, '4': 1, '5': 8, '9': 5, '10': 'asrEnabled', '17': true},
    {'1': 'tts_enabled', '3': 7, '4': 1, '5': 8, '9': 6, '10': 'ttsEnabled', '17': true},
    {'1': 'read_aloud_mode', '3': 8, '4': 1, '5': 8, '9': 7, '10': 'readAloudMode', '17': true},
    {'1': 'persona', '3': 9, '4': 1, '5': 9, '9': 8, '10': 'persona', '17': true},
    {'1': 'user_name', '3': 10, '4': 1, '5': 9, '9': 9, '10': 'userName', '17': true},
  ],
  '8': [
    {'1': '_model'},
    {'1': '_voice'},
    {'1': '_render_backend'},
    {'1': '_always_on_top'},
    {'1': '_auto_start'},
    {'1': '_asr_enabled'},
    {'1': '_tts_enabled'},
    {'1': '_read_aloud_mode'},
    {'1': '_persona'},
    {'1': '_user_name'},
  ],
};

/// Descriptor for `SettingsRequest`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List settingsRequestDescriptor = $convert.base64Decode(
    'Cg9TZXR0aW5nc1JlcXVlc3QSGQoFbW9kZWwYASABKAlIAFIFbW9kZWyIAQESGQoFdm9pY2UYAi'
    'ABKAlIAVIFdm9pY2WIAQESKgoOcmVuZGVyX2JhY2tlbmQYAyABKAlIAlINcmVuZGVyQmFja2Vu'
    'ZIgBARInCg1hbHdheXNfb25fdG9wGAQgASgISANSC2Fsd2F5c09uVG9wiAEBEiIKCmF1dG9fc3'
    'RhcnQYBSABKAhIBFIJYXV0b1N0YXJ0iAEBEiQKC2Fzcl9lbmFibGVkGAYgASgISAVSCmFzckVu'
    'YWJsZWSIAQESJAoLdHRzX2VuYWJsZWQYByABKAhIBlIKdHRzRW5hYmxlZIgBARIrCg9yZWFkX2'
    'Fsb3VkX21vZGUYCCABKAhIB1INcmVhZEFsb3VkTW9kZYgBARIdCgdwZXJzb25hGAkgASgJSAhS'
    'B3BlcnNvbmGIAQESIAoJdXNlcl9uYW1lGAogASgJSAlSCHVzZXJOYW1liAEBQggKBl9tb2RlbE'
    'IICgZfdm9pY2VCEQoPX3JlbmRlcl9iYWNrZW5kQhAKDl9hbHdheXNfb25fdG9wQg0KC19hdXRv'
    'X3N0YXJ0Qg4KDF9hc3JfZW5hYmxlZEIOCgxfdHRzX2VuYWJsZWRCEgoQX3JlYWRfYWxvdWRfbW'
    '9kZUIKCghfcGVyc29uYUIMCgpfdXNlcl9uYW1l');

@$core.Deprecated('Use personaReplyDescriptor instead')
const PersonaReply$json = {
  '1': 'PersonaReply',
  '2': [
    {'1': 'emotion', '3': 1, '4': 1, '5': 9, '10': 'emotion'},
    {'1': 'emotion_intensity', '3': 2, '4': 1, '5': 1, '10': 'emotionIntensity'},
    {'1': 'relationship', '3': 3, '4': 1, '5': 9, '10': 'relationship'},
    {'1': 'relationship_score', '3': 4, '4': 1, '5': 1, '10': 'relationshipScore'},
    {'1': 'relationship_progress', '3': 5, '4': 1, '5': 1, '10': 'relationshipProgress'},
    {'1': 'reminders_pending', '3': 6, '4': 1, '5': 5, '10': 'remindersPending'},
    {'1': 'persona', '3': 7, '4': 1, '5': 9, '10': 'persona'},
    {'1': 'user_name', '3': 8, '4': 1, '5': 9, '10': 'userName'},
    {'1': 'axes', '3': 9, '4': 3, '5': 11, '6': '.xiaoling.PersonaAxis', '10': 'axes'},
  ],
};

/// Descriptor for `PersonaReply`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List personaReplyDescriptor = $convert.base64Decode(
    'CgxQZXJzb25hUmVwbHkSGAoHZW1vdGlvbhgBIAEoCVIHZW1vdGlvbhIrChFlbW90aW9uX2ludG'
    'Vuc2l0eRgCIAEoAVIQZW1vdGlvbkludGVuc2l0eRIiCgxyZWxhdGlvbnNoaXAYAyABKAlSDHJl'
    'bGF0aW9uc2hpcBItChJyZWxhdGlvbnNoaXBfc2NvcmUYBCABKAFSEXJlbGF0aW9uc2hpcFNjb3'
    'JlEjMKFXJlbGF0aW9uc2hpcF9wcm9ncmVzcxgFIAEoAVIUcmVsYXRpb25zaGlwUHJvZ3Jlc3MS'
    'KwoRcmVtaW5kZXJzX3BlbmRpbmcYBiABKAVSEHJlbWluZGVyc1BlbmRpbmcSGAoHcGVyc29uYR'
    'gHIAEoCVIHcGVyc29uYRIbCgl1c2VyX25hbWUYCCABKAlSCHVzZXJOYW1lEikKBGF4ZXMYCSAD'
    'KAsyFS54aWFvbGluZy5QZXJzb25hQXhpc1IEYXhlcw==');

@$core.Deprecated('Use personaAxisDescriptor instead')
const PersonaAxis$json = {
  '1': 'PersonaAxis',
  '2': [
    {'1': 'name', '3': 1, '4': 1, '5': 9, '10': 'name'},
    {'1': 'label', '3': 2, '4': 1, '5': 9, '10': 'label'},
    {'1': 'value', '3': 3, '4': 1, '5': 1, '10': 'value'},
  ],
};

/// Descriptor for `PersonaAxis`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List personaAxisDescriptor = $convert.base64Decode(
    'CgtQZXJzb25hQXhpcxISCgRuYW1lGAEgASgJUgRuYW1lEhQKBWxhYmVsGAIgASgJUgVsYWJlbB'
    'IUCgV2YWx1ZRgDIAEoAVIFdmFsdWU=');

@$core.Deprecated('Use personaPresetDescriptor instead')
const PersonaPreset$json = {
  '1': 'PersonaPreset',
  '2': [
    {'1': 'id', '3': 1, '4': 1, '5': 9, '10': 'id'},
    {'1': 'name', '3': 2, '4': 1, '5': 9, '10': 'name'},
    {'1': 'description', '3': 3, '4': 1, '5': 9, '10': 'description'},
    {'1': 'prompt_hint', '3': 4, '4': 1, '5': 9, '10': 'promptHint'},
    {'1': 'builtin', '3': 5, '4': 1, '5': 8, '10': 'builtin'},
    {'1': 'active', '3': 6, '4': 1, '5': 8, '10': 'active'},
  ],
};

/// Descriptor for `PersonaPreset`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List personaPresetDescriptor = $convert.base64Decode(
    'Cg1QZXJzb25hUHJlc2V0Eg4KAmlkGAEgASgJUgJpZBISCgRuYW1lGAIgASgJUgRuYW1lEiAKC2'
    'Rlc2NyaXB0aW9uGAMgASgJUgtkZXNjcmlwdGlvbhIfCgtwcm9tcHRfaGludBgEIAEoCVIKcHJv'
    'bXB0SGludBIYCgdidWlsdGluGAUgASgIUgdidWlsdGluEhYKBmFjdGl2ZRgGIAEoCFIGYWN0aX'
    'Zl');

@$core.Deprecated('Use personaListDescriptor instead')
const PersonaList$json = {
  '1': 'PersonaList',
  '2': [
    {'1': 'presets', '3': 1, '4': 3, '5': 11, '6': '.xiaoling.PersonaPreset', '10': 'presets'},
  ],
};

/// Descriptor for `PersonaList`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List personaListDescriptor = $convert.base64Decode(
    'CgtQZXJzb25hTGlzdBIxCgdwcmVzZXRzGAEgAygLMhcueGlhb2xpbmcuUGVyc29uYVByZXNldF'
    'IHcHJlc2V0cw==');

@$core.Deprecated('Use personaRequestDescriptor instead')
const PersonaRequest$json = {
  '1': 'PersonaRequest',
  '2': [
    {'1': 'id', '3': 1, '4': 1, '5': 9, '10': 'id'},
    {'1': 'name', '3': 2, '4': 1, '5': 9, '10': 'name'},
    {'1': 'description', '3': 3, '4': 1, '5': 9, '10': 'description'},
    {'1': 'prompt_hint', '3': 4, '4': 1, '5': 9, '10': 'promptHint'},
  ],
};

/// Descriptor for `PersonaRequest`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List personaRequestDescriptor = $convert.base64Decode(
    'Cg5QZXJzb25hUmVxdWVzdBIOCgJpZBgBIAEoCVICaWQSEgoEbmFtZRgCIAEoCVIEbmFtZRIgCg'
    'tkZXNjcmlwdGlvbhgDIAEoCVILZGVzY3JpcHRpb24SHwoLcHJvbXB0X2hpbnQYBCABKAlSCnBy'
    'b21wdEhpbnQ=');

@$core.Deprecated('Use reminderItemDescriptor instead')
const ReminderItem$json = {
  '1': 'ReminderItem',
  '2': [
    {'1': 'text', '3': 1, '4': 1, '5': 9, '10': 'text'},
    {'1': 'due_at', '3': 2, '4': 1, '5': 1, '10': 'dueAt'},
    {'1': 'done', '3': 3, '4': 1, '5': 8, '10': 'done'},
    {'1': 'created_at', '3': 4, '4': 1, '5': 1, '10': 'createdAt'},
    {'1': 'seconds_left', '3': 5, '4': 1, '5': 3, '10': 'secondsLeft'},
  ],
};

/// Descriptor for `ReminderItem`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List reminderItemDescriptor = $convert.base64Decode(
    'CgxSZW1pbmRlckl0ZW0SEgoEdGV4dBgBIAEoCVIEdGV4dBIVCgZkdWVfYXQYAiABKAFSBWR1ZU'
    'F0EhIKBGRvbmUYAyABKAhSBGRvbmUSHQoKY3JlYXRlZF9hdBgEIAEoAVIJY3JlYXRlZEF0EiEK'
    'DHNlY29uZHNfbGVmdBgFIAEoA1ILc2Vjb25kc0xlZnQ=');

@$core.Deprecated('Use reminderListDescriptor instead')
const ReminderList$json = {
  '1': 'ReminderList',
  '2': [
    {'1': 'items', '3': 1, '4': 3, '5': 11, '6': '.xiaoling.ReminderItem', '10': 'items'},
    {'1': 'unread', '3': 2, '4': 1, '5': 5, '10': 'unread'},
    {'1': 'pending', '3': 3, '4': 1, '5': 5, '10': 'pending'},
  ],
};

/// Descriptor for `ReminderList`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List reminderListDescriptor = $convert.base64Decode(
    'CgxSZW1pbmRlckxpc3QSLAoFaXRlbXMYASADKAsyFi54aWFvbGluZy5SZW1pbmRlckl0ZW1SBW'
    'l0ZW1zEhYKBnVucmVhZBgCIAEoBVIGdW5yZWFkEhgKB3BlbmRpbmcYAyABKAVSB3BlbmRpbmc=');

@$core.Deprecated('Use reminderRequestDescriptor instead')
const ReminderRequest$json = {
  '1': 'ReminderRequest',
  '2': [
    {'1': 'due_at', '3': 1, '4': 1, '5': 1, '10': 'dueAt'},
  ],
};

/// Descriptor for `ReminderRequest`. Decode as a `google.protobuf.DescriptorProto`.
final $typed_data.Uint8List reminderRequestDescriptor = $convert.base64Decode(
    'Cg9SZW1pbmRlclJlcXVlc3QSFQoGZHVlX2F0GAEgASgBUgVkdWVBdA==');

