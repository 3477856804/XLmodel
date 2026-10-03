//
//  Generated code. Do not modify.
//  source: xiaoling.proto
//
// @dart = 3.3

// ignore_for_file: annotate_overrides, camel_case_types, comment_references
// ignore_for_file: constant_identifier_names, library_prefixes
// ignore_for_file: non_constant_identifier_names, prefer_final_fields
// ignore_for_file: unnecessary_import, unnecessary_this, unused_import

import 'dart:async' as $async;
import 'dart:core' as $core;

import 'package:grpc/service_api.dart' as $grpc;
import 'package:protobuf/protobuf.dart' as $pb;

import 'xiaoling.pb.dart' as $0;

export 'xiaoling.pb.dart';

@$pb.GrpcServiceName('xiaoling.XiaoLing')
class XiaoLingClient extends $grpc.Client {
  static final _$chat = $grpc.ClientMethod<$0.ChatRequest, $0.ChatChunk>(
      '/xiaoling.XiaoLing/Chat',
      ($0.ChatRequest value) => value.writeToBuffer(),
      ($core.List<$core.int> value) => $0.ChatChunk.fromBuffer(value));
  static final _$getStatus = $grpc.ClientMethod<$0.StatusRequest, $0.StatusReply>(
      '/xiaoling.XiaoLing/GetStatus',
      ($0.StatusRequest value) => value.writeToBuffer(),
      ($core.List<$core.int> value) => $0.StatusReply.fromBuffer(value));
  static final _$getGrowthStatus = $grpc.ClientMethod<$0.Empty, $0.GrowthStatusReply>(
      '/xiaoling.XiaoLing/GetGrowthStatus',
      ($0.Empty value) => value.writeToBuffer(),
      ($core.List<$core.int> value) => $0.GrowthStatusReply.fromBuffer(value));
  static final _$getTrainingStatus = $grpc.ClientMethod<$0.Empty, $0.TrainingStatusReply>(
      '/xiaoling.XiaoLing/GetTrainingStatus',
      ($0.Empty value) => value.writeToBuffer(),
      ($core.List<$core.int> value) => $0.TrainingStatusReply.fromBuffer(value));
  static final _$listPlugins = $grpc.ClientMethod<$0.Empty, $0.PluginList>(
      '/xiaoling.XiaoLing/ListPlugins',
      ($0.Empty value) => value.writeToBuffer(),
      ($core.List<$core.int> value) => $0.PluginList.fromBuffer(value));
  static final _$listModels = $grpc.ClientMethod<$0.ListRequest, $0.ModelList>(
      '/xiaoling.XiaoLing/ListModels',
      ($0.ListRequest value) => value.writeToBuffer(),
      ($core.List<$core.int> value) => $0.ModelList.fromBuffer(value));
  static final _$switchModel = $grpc.ClientMethod<$0.SwitchModelRequest, $0.StatusReply>(
      '/xiaoling.XiaoLing/SwitchModel',
      ($0.SwitchModelRequest value) => value.writeToBuffer(),
      ($core.List<$core.int> value) => $0.StatusReply.fromBuffer(value));
  static final _$listActions = $grpc.ClientMethod<$0.ListRequest, $0.ActionList>(
      '/xiaoling.XiaoLing/ListActions',
      ($0.ListRequest value) => value.writeToBuffer(),
      ($core.List<$core.int> value) => $0.ActionList.fromBuffer(value));
  static final _$playAction = $grpc.ClientMethod<$0.PlayActionRequest, $0.StatusReply>(
      '/xiaoling.XiaoLing/PlayAction',
      ($0.PlayActionRequest value) => value.writeToBuffer(),
      ($core.List<$core.int> value) => $0.StatusReply.fromBuffer(value));
  static final _$executeCommand = $grpc.ClientMethod<$0.CommandRequest, $0.CommandReply>(
      '/xiaoling.XiaoLing/ExecuteCommand',
      ($0.CommandRequest value) => value.writeToBuffer(),
      ($core.List<$core.int> value) => $0.CommandReply.fromBuffer(value));
  static final _$shutdown = $grpc.ClientMethod<$0.ShutdownRequest, $0.StatusReply>(
      '/xiaoling.XiaoLing/Shutdown',
      ($0.ShutdownRequest value) => value.writeToBuffer(),
      ($core.List<$core.int> value) => $0.StatusReply.fromBuffer(value));
  static final _$detectHardware = $grpc.ClientMethod<$0.Empty, $0.HardwareInfo>(
      '/xiaoling.XiaoLing/DetectHardware',
      ($0.Empty value) => value.writeToBuffer(),
      ($core.List<$core.int> value) => $0.HardwareInfo.fromBuffer(value));
  static final _$listRecommendedModels = $grpc.ClientMethod<$0.HardwareRequest, $0.RecommendedModelList>(
      '/xiaoling.XiaoLing/ListRecommendedModels',
      ($0.HardwareRequest value) => value.writeToBuffer(),
      ($core.List<$core.int> value) => $0.RecommendedModelList.fromBuffer(value));
  static final _$downloadModel = $grpc.ClientMethod<$0.DownloadRequest, $0.DownloadProgress>(
      '/xiaoling.XiaoLing/DownloadModel',
      ($0.DownloadRequest value) => value.writeToBuffer(),
      ($core.List<$core.int> value) => $0.DownloadProgress.fromBuffer(value));
  static final _$listInstalledModels = $grpc.ClientMethod<$0.Empty, $0.ModelList>(
      '/xiaoling.XiaoLing/ListInstalledModels',
      ($0.Empty value) => value.writeToBuffer(),
      ($core.List<$core.int> value) => $0.ModelList.fromBuffer(value));
  static final _$deleteModel = $grpc.ClientMethod<$0.ModelNameRequest, $0.StatusReply>(
      '/xiaoling.XiaoLing/DeleteModel',
      ($0.ModelNameRequest value) => value.writeToBuffer(),
      ($core.List<$core.int> value) => $0.StatusReply.fromBuffer(value));
  static final _$listVoices = $grpc.ClientMethod<$0.Empty, $0.VoiceList>(
      '/xiaoling.XiaoLing/ListVoices',
      ($0.Empty value) => value.writeToBuffer(),
      ($core.List<$core.int> value) => $0.VoiceList.fromBuffer(value));
  static final _$setVoice = $grpc.ClientMethod<$0.VoiceRequest, $0.StatusReply>(
      '/xiaoling.XiaoLing/SetVoice',
      ($0.VoiceRequest value) => value.writeToBuffer(),
      ($core.List<$core.int> value) => $0.StatusReply.fromBuffer(value));
  static final _$readAloud = $grpc.ClientMethod<$0.ReadRequest, $0.AudioChunk>(
      '/xiaoling.XiaoLing/ReadAloud',
      ($0.ReadRequest value) => value.writeToBuffer(),
      ($core.List<$core.int> value) => $0.AudioChunk.fromBuffer(value));
  static final _$getSettings = $grpc.ClientMethod<$0.Empty, $0.SettingsReply>(
      '/xiaoling.XiaoLing/GetSettings',
      ($0.Empty value) => value.writeToBuffer(),
      ($core.List<$core.int> value) => $0.SettingsReply.fromBuffer(value));
  static final _$updateSettings = $grpc.ClientMethod<$0.SettingsRequest, $0.StatusReply>(
      '/xiaoling.XiaoLing/UpdateSettings',
      ($0.SettingsRequest value) => value.writeToBuffer(),
      ($core.List<$core.int> value) => $0.StatusReply.fromBuffer(value));

  XiaoLingClient(super.channel, {super.options, super.interceptors});

  $grpc.ResponseStream<$0.ChatChunk> chat($0.ChatRequest request, {$grpc.CallOptions? options}) {
    return $createStreamingCall(_$chat, $async.Stream.fromIterable([request]), options: options);
  }

  $grpc.ResponseFuture<$0.StatusReply> getStatus($0.StatusRequest request, {$grpc.CallOptions? options}) {
    return $createUnaryCall(_$getStatus, request, options: options);
  }

  $grpc.ResponseFuture<$0.GrowthStatusReply> getGrowthStatus($0.Empty request, {$grpc.CallOptions? options}) {
    return $createUnaryCall(_$getGrowthStatus, request, options: options);
  }

  $grpc.ResponseFuture<$0.TrainingStatusReply> getTrainingStatus($0.Empty request, {$grpc.CallOptions? options}) {
    return $createUnaryCall(_$getTrainingStatus, request, options: options);
  }

  $grpc.ResponseFuture<$0.PluginList> listPlugins($0.Empty request, {$grpc.CallOptions? options}) {
    return $createUnaryCall(_$listPlugins, request, options: options);
  }

  $grpc.ResponseFuture<$0.ModelList> listModels($0.ListRequest request, {$grpc.CallOptions? options}) {
    return $createUnaryCall(_$listModels, request, options: options);
  }

  $grpc.ResponseFuture<$0.StatusReply> switchModel($0.SwitchModelRequest request, {$grpc.CallOptions? options}) {
    return $createUnaryCall(_$switchModel, request, options: options);
  }

  $grpc.ResponseFuture<$0.ActionList> listActions($0.ListRequest request, {$grpc.CallOptions? options}) {
    return $createUnaryCall(_$listActions, request, options: options);
  }

  $grpc.ResponseFuture<$0.StatusReply> playAction($0.PlayActionRequest request, {$grpc.CallOptions? options}) {
    return $createUnaryCall(_$playAction, request, options: options);
  }

  $grpc.ResponseFuture<$0.CommandReply> executeCommand($0.CommandRequest request, {$grpc.CallOptions? options}) {
    return $createUnaryCall(_$executeCommand, request, options: options);
  }

  $grpc.ResponseFuture<$0.StatusReply> shutdown($0.ShutdownRequest request, {$grpc.CallOptions? options}) {
    return $createUnaryCall(_$shutdown, request, options: options);
  }

  $grpc.ResponseFuture<$0.HardwareInfo> detectHardware($0.Empty request, {$grpc.CallOptions? options}) {
    return $createUnaryCall(_$detectHardware, request, options: options);
  }

  $grpc.ResponseFuture<$0.RecommendedModelList> listRecommendedModels($0.HardwareRequest request, {$grpc.CallOptions? options}) {
    return $createUnaryCall(_$listRecommendedModels, request, options: options);
  }

  $grpc.ResponseStream<$0.DownloadProgress> downloadModel($0.DownloadRequest request, {$grpc.CallOptions? options}) {
    return $createStreamingCall(_$downloadModel, $async.Stream.fromIterable([request]), options: options);
  }

  $grpc.ResponseFuture<$0.ModelList> listInstalledModels($0.Empty request, {$grpc.CallOptions? options}) {
    return $createUnaryCall(_$listInstalledModels, request, options: options);
  }

  $grpc.ResponseFuture<$0.StatusReply> deleteModel($0.ModelNameRequest request, {$grpc.CallOptions? options}) {
    return $createUnaryCall(_$deleteModel, request, options: options);
  }

  $grpc.ResponseFuture<$0.VoiceList> listVoices($0.Empty request, {$grpc.CallOptions? options}) {
    return $createUnaryCall(_$listVoices, request, options: options);
  }

  $grpc.ResponseFuture<$0.StatusReply> setVoice($0.VoiceRequest request, {$grpc.CallOptions? options}) {
    return $createUnaryCall(_$setVoice, request, options: options);
  }

  $grpc.ResponseStream<$0.AudioChunk> readAloud($0.ReadRequest request, {$grpc.CallOptions? options}) {
    return $createStreamingCall(_$readAloud, $async.Stream.fromIterable([request]), options: options);
  }

  $grpc.ResponseFuture<$0.SettingsReply> getSettings($0.Empty request, {$grpc.CallOptions? options}) {
    return $createUnaryCall(_$getSettings, request, options: options);
  }

  $grpc.ResponseFuture<$0.StatusReply> updateSettings($0.SettingsRequest request, {$grpc.CallOptions? options}) {
    return $createUnaryCall(_$updateSettings, request, options: options);
  }
}

@$pb.GrpcServiceName('xiaoling.XiaoLing')
abstract class XiaoLingServiceBase extends $grpc.Service {
  $core.String get $name => 'xiaoling.XiaoLing';

  XiaoLingServiceBase() {
    $addMethod($grpc.ServiceMethod<$0.ChatRequest, $0.ChatChunk>(
        'Chat',
        chat_Pre,
        false,
        true,
        ($core.List<$core.int> value) => $0.ChatRequest.fromBuffer(value),
        ($0.ChatChunk value) => value.writeToBuffer()));
    $addMethod($grpc.ServiceMethod<$0.StatusRequest, $0.StatusReply>(
        'GetStatus',
        getStatus_Pre,
        false,
        false,
        ($core.List<$core.int> value) => $0.StatusRequest.fromBuffer(value),
        ($0.StatusReply value) => value.writeToBuffer()));
    $addMethod($grpc.ServiceMethod<$0.Empty, $0.GrowthStatusReply>(
        'GetGrowthStatus',
        getGrowthStatus_Pre,
        false,
        false,
        ($core.List<$core.int> value) => $0.Empty.fromBuffer(value),
        ($0.GrowthStatusReply value) => value.writeToBuffer()));
    $addMethod($grpc.ServiceMethod<$0.Empty, $0.TrainingStatusReply>(
        'GetTrainingStatus',
        getTrainingStatus_Pre,
        false,
        false,
        ($core.List<$core.int> value) => $0.Empty.fromBuffer(value),
        ($0.TrainingStatusReply value) => value.writeToBuffer()));
    $addMethod($grpc.ServiceMethod<$0.Empty, $0.PluginList>(
        'ListPlugins',
        listPlugins_Pre,
        false,
        false,
        ($core.List<$core.int> value) => $0.Empty.fromBuffer(value),
        ($0.PluginList value) => value.writeToBuffer()));
    $addMethod($grpc.ServiceMethod<$0.ListRequest, $0.ModelList>(
        'ListModels',
        listModels_Pre,
        false,
        false,
        ($core.List<$core.int> value) => $0.ListRequest.fromBuffer(value),
        ($0.ModelList value) => value.writeToBuffer()));
    $addMethod($grpc.ServiceMethod<$0.SwitchModelRequest, $0.StatusReply>(
        'SwitchModel',
        switchModel_Pre,
        false,
        false,
        ($core.List<$core.int> value) => $0.SwitchModelRequest.fromBuffer(value),
        ($0.StatusReply value) => value.writeToBuffer()));
    $addMethod($grpc.ServiceMethod<$0.ListRequest, $0.ActionList>(
        'ListActions',
        listActions_Pre,
        false,
        false,
        ($core.List<$core.int> value) => $0.ListRequest.fromBuffer(value),
        ($0.ActionList value) => value.writeToBuffer()));
    $addMethod($grpc.ServiceMethod<$0.PlayActionRequest, $0.StatusReply>(
        'PlayAction',
        playAction_Pre,
        false,
        false,
        ($core.List<$core.int> value) => $0.PlayActionRequest.fromBuffer(value),
        ($0.StatusReply value) => value.writeToBuffer()));
    $addMethod($grpc.ServiceMethod<$0.CommandRequest, $0.CommandReply>(
        'ExecuteCommand',
        executeCommand_Pre,
        false,
        false,
        ($core.List<$core.int> value) => $0.CommandRequest.fromBuffer(value),
        ($0.CommandReply value) => value.writeToBuffer()));
    $addMethod($grpc.ServiceMethod<$0.ShutdownRequest, $0.StatusReply>(
        'Shutdown',
        shutdown_Pre,
        false,
        false,
        ($core.List<$core.int> value) => $0.ShutdownRequest.fromBuffer(value),
        ($0.StatusReply value) => value.writeToBuffer()));
    $addMethod($grpc.ServiceMethod<$0.Empty, $0.HardwareInfo>(
        'DetectHardware',
        detectHardware_Pre,
        false,
        false,
        ($core.List<$core.int> value) => $0.Empty.fromBuffer(value),
        ($0.HardwareInfo value) => value.writeToBuffer()));
    $addMethod($grpc.ServiceMethod<$0.HardwareRequest, $0.RecommendedModelList>(
        'ListRecommendedModels',
        listRecommendedModels_Pre,
        false,
        false,
        ($core.List<$core.int> value) => $0.HardwareRequest.fromBuffer(value),
        ($0.RecommendedModelList value) => value.writeToBuffer()));
    $addMethod($grpc.ServiceMethod<$0.DownloadRequest, $0.DownloadProgress>(
        'DownloadModel',
        downloadModel_Pre,
        false,
        true,
        ($core.List<$core.int> value) => $0.DownloadRequest.fromBuffer(value),
        ($0.DownloadProgress value) => value.writeToBuffer()));
    $addMethod($grpc.ServiceMethod<$0.Empty, $0.ModelList>(
        'ListInstalledModels',
        listInstalledModels_Pre,
        false,
        false,
        ($core.List<$core.int> value) => $0.Empty.fromBuffer(value),
        ($0.ModelList value) => value.writeToBuffer()));
    $addMethod($grpc.ServiceMethod<$0.ModelNameRequest, $0.StatusReply>(
        'DeleteModel',
        deleteModel_Pre,
        false,
        false,
        ($core.List<$core.int> value) => $0.ModelNameRequest.fromBuffer(value),
        ($0.StatusReply value) => value.writeToBuffer()));
    $addMethod($grpc.ServiceMethod<$0.Empty, $0.VoiceList>(
        'ListVoices',
        listVoices_Pre,
        false,
        false,
        ($core.List<$core.int> value) => $0.Empty.fromBuffer(value),
        ($0.VoiceList value) => value.writeToBuffer()));
    $addMethod($grpc.ServiceMethod<$0.VoiceRequest, $0.StatusReply>(
        'SetVoice',
        setVoice_Pre,
        false,
        false,
        ($core.List<$core.int> value) => $0.VoiceRequest.fromBuffer(value),
        ($0.StatusReply value) => value.writeToBuffer()));
    $addMethod($grpc.ServiceMethod<$0.ReadRequest, $0.AudioChunk>(
        'ReadAloud',
        readAloud_Pre,
        false,
        true,
        ($core.List<$core.int> value) => $0.ReadRequest.fromBuffer(value),
        ($0.AudioChunk value) => value.writeToBuffer()));
    $addMethod($grpc.ServiceMethod<$0.Empty, $0.SettingsReply>(
        'GetSettings',
        getSettings_Pre,
        false,
        false,
        ($core.List<$core.int> value) => $0.Empty.fromBuffer(value),
        ($0.SettingsReply value) => value.writeToBuffer()));
    $addMethod($grpc.ServiceMethod<$0.SettingsRequest, $0.StatusReply>(
        'UpdateSettings',
        updateSettings_Pre,
        false,
        false,
        ($core.List<$core.int> value) => $0.SettingsRequest.fromBuffer(value),
        ($0.StatusReply value) => value.writeToBuffer()));
  }

  $async.Stream<$0.ChatChunk> chat_Pre($grpc.ServiceCall $call, $async.Future<$0.ChatRequest> $request) async* {
    yield* chat($call, await $request);
  }

  $async.Future<$0.StatusReply> getStatus_Pre($grpc.ServiceCall $call, $async.Future<$0.StatusRequest> $request) async {
    return getStatus($call, await $request);
  }

  $async.Future<$0.GrowthStatusReply> getGrowthStatus_Pre($grpc.ServiceCall $call, $async.Future<$0.Empty> $request) async {
    return getGrowthStatus($call, await $request);
  }

  $async.Future<$0.TrainingStatusReply> getTrainingStatus_Pre($grpc.ServiceCall $call, $async.Future<$0.Empty> $request) async {
    return getTrainingStatus($call, await $request);
  }

  $async.Future<$0.PluginList> listPlugins_Pre($grpc.ServiceCall $call, $async.Future<$0.Empty> $request) async {
    return listPlugins($call, await $request);
  }

  $async.Future<$0.ModelList> listModels_Pre($grpc.ServiceCall $call, $async.Future<$0.ListRequest> $request) async {
    return listModels($call, await $request);
  }

  $async.Future<$0.StatusReply> switchModel_Pre($grpc.ServiceCall $call, $async.Future<$0.SwitchModelRequest> $request) async {
    return switchModel($call, await $request);
  }

  $async.Future<$0.ActionList> listActions_Pre($grpc.ServiceCall $call, $async.Future<$0.ListRequest> $request) async {
    return listActions($call, await $request);
  }

  $async.Future<$0.StatusReply> playAction_Pre($grpc.ServiceCall $call, $async.Future<$0.PlayActionRequest> $request) async {
    return playAction($call, await $request);
  }

  $async.Future<$0.CommandReply> executeCommand_Pre($grpc.ServiceCall $call, $async.Future<$0.CommandRequest> $request) async {
    return executeCommand($call, await $request);
  }

  $async.Future<$0.StatusReply> shutdown_Pre($grpc.ServiceCall $call, $async.Future<$0.ShutdownRequest> $request) async {
    return shutdown($call, await $request);
  }

  $async.Future<$0.HardwareInfo> detectHardware_Pre($grpc.ServiceCall $call, $async.Future<$0.Empty> $request) async {
    return detectHardware($call, await $request);
  }

  $async.Future<$0.RecommendedModelList> listRecommendedModels_Pre($grpc.ServiceCall $call, $async.Future<$0.HardwareRequest> $request) async {
    return listRecommendedModels($call, await $request);
  }

  $async.Stream<$0.DownloadProgress> downloadModel_Pre($grpc.ServiceCall $call, $async.Future<$0.DownloadRequest> $request) async* {
    yield* downloadModel($call, await $request);
  }

  $async.Future<$0.ModelList> listInstalledModels_Pre($grpc.ServiceCall $call, $async.Future<$0.Empty> $request) async {
    return listInstalledModels($call, await $request);
  }

  $async.Future<$0.StatusReply> deleteModel_Pre($grpc.ServiceCall $call, $async.Future<$0.ModelNameRequest> $request) async {
    return deleteModel($call, await $request);
  }

  $async.Future<$0.VoiceList> listVoices_Pre($grpc.ServiceCall $call, $async.Future<$0.Empty> $request) async {
    return listVoices($call, await $request);
  }

  $async.Future<$0.StatusReply> setVoice_Pre($grpc.ServiceCall $call, $async.Future<$0.VoiceRequest> $request) async {
    return setVoice($call, await $request);
  }

  $async.Stream<$0.AudioChunk> readAloud_Pre($grpc.ServiceCall $call, $async.Future<$0.ReadRequest> $request) async* {
    yield* readAloud($call, await $request);
  }

  $async.Future<$0.SettingsReply> getSettings_Pre($grpc.ServiceCall $call, $async.Future<$0.Empty> $request) async {
    return getSettings($call, await $request);
  }

  $async.Future<$0.StatusReply> updateSettings_Pre($grpc.ServiceCall $call, $async.Future<$0.SettingsRequest> $request) async {
    return updateSettings($call, await $request);
  }

  $async.Stream<$0.ChatChunk> chat($grpc.ServiceCall call, $0.ChatRequest request);
  $async.Future<$0.StatusReply> getStatus($grpc.ServiceCall call, $0.StatusRequest request);
  $async.Future<$0.GrowthStatusReply> getGrowthStatus($grpc.ServiceCall call, $0.Empty request);
  $async.Future<$0.TrainingStatusReply> getTrainingStatus($grpc.ServiceCall call, $0.Empty request);
  $async.Future<$0.PluginList> listPlugins($grpc.ServiceCall call, $0.Empty request);
  $async.Future<$0.ModelList> listModels($grpc.ServiceCall call, $0.ListRequest request);
  $async.Future<$0.StatusReply> switchModel($grpc.ServiceCall call, $0.SwitchModelRequest request);
  $async.Future<$0.ActionList> listActions($grpc.ServiceCall call, $0.ListRequest request);
  $async.Future<$0.StatusReply> playAction($grpc.ServiceCall call, $0.PlayActionRequest request);
  $async.Future<$0.CommandReply> executeCommand($grpc.ServiceCall call, $0.CommandRequest request);
  $async.Future<$0.StatusReply> shutdown($grpc.ServiceCall call, $0.ShutdownRequest request);
  $async.Future<$0.HardwareInfo> detectHardware($grpc.ServiceCall call, $0.Empty request);
  $async.Future<$0.RecommendedModelList> listRecommendedModels($grpc.ServiceCall call, $0.HardwareRequest request);
  $async.Stream<$0.DownloadProgress> downloadModel($grpc.ServiceCall call, $0.DownloadRequest request);
  $async.Future<$0.ModelList> listInstalledModels($grpc.ServiceCall call, $0.Empty request);
  $async.Future<$0.StatusReply> deleteModel($grpc.ServiceCall call, $0.ModelNameRequest request);
  $async.Future<$0.VoiceList> listVoices($grpc.ServiceCall call, $0.Empty request);
  $async.Future<$0.StatusReply> setVoice($grpc.ServiceCall call, $0.VoiceRequest request);
  $async.Stream<$0.AudioChunk> readAloud($grpc.ServiceCall call, $0.ReadRequest request);
  $async.Future<$0.SettingsReply> getSettings($grpc.ServiceCall call, $0.Empty request);
  $async.Future<$0.StatusReply> updateSettings($grpc.ServiceCall call, $0.SettingsRequest request);
}
