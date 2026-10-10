package com.vocalis.companion

import android.media.MediaCodec
import android.media.MediaCodecInfo
import android.media.MediaFormat
import android.media.MediaMuxer
import io.flutter.embedding.android.FlutterFragmentActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import java.io.File
import java.io.FileInputStream
import java.nio.ByteBuffer

/**
 * Canal "vocalis_companion/audio" → compressToAac.
 * WAV PCM16 mono 44.1 kHz → AAC/m4a mono ~48 kbps con MediaCodec + MediaMuxer.
 * Lectura por streaming (no carga el WAV completo en memoria).
 */
class MainActivity : FlutterFragmentActivity() {
    private val channel = "vocalis_companion/audio"

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, channel)
            .setMethodCallHandler { call, result ->
                if (call.method == "compressToAac") {
                    try {
                        val input = call.argument<String>("in")!!
                        val output = call.argument<String>("out")!!
                        val bitrate = call.argument<Int>("bitrate") ?: 48000
                        encodeWavToAac(input, output, bitrate)
                        result.success(true)
                    } catch (e: Exception) {
                        result.error("AAC", e.message, null)
                    }
                } else {
                    result.notImplemented()
                }
            }
    }

    private fun encodeWavToAac(inPath: String, outPath: String, bitrate: Int) {
        val sampleRate = 44100
        val format = MediaFormat.createAudioFormat(
            MediaFormat.MIMETYPE_AUDIO_AAC, sampleRate, 1)
        format.setInteger(MediaFormat.KEY_AAC_PROFILE,
            MediaCodecInfo.CodecProfileLevel.AACObjectLC)
        format.setInteger(MediaFormat.KEY_BIT_RATE, bitrate)
        format.setInteger(MediaFormat.KEY_MAX_INPUT_SIZE, 64 * 1024)

        val codec = MediaCodec.createEncoderByType(MediaFormat.MIMETYPE_AUDIO_AAC)
        codec.configure(format, null, null, MediaCodec.CONFIGURE_FLAG_ENCODE)
        codec.start()

        var muxer: MediaMuxer? = null
        var track = -1
        var muxerStarted = false
        val fis = FileInputStream(File(inPath))
        // Saltear cabecera WAV de 44 bytes.
        var skipped = 0L
        while (skipped < 44) {
            val n = fis.skip(44 - skipped)
            if (n <= 0) break
            skipped += n
        }
        val buf = ByteArray(32 * 1024)
        var eosEnviado = false
        var presentationUs = 0L
        // 16-bit mono 44.1 kHz → 88200 bytes/s.
        try {
            while (true) {
                if (!eosEnviado) {
                    val idx = codec.dequeueInputBuffer(10_000)
                    if (idx >= 0) {
                        val input = codec.getInputBuffer(idx)!!
                        input.clear()
                        val read = fis.read(buf, 0, minOf(buf.size, input.remaining()))
                        if (read <= 0) {
                            codec.queueInputBuffer(idx, 0, 0, 0,
                                MediaCodec.BUFFER_FLAG_END_OF_STREAM)
                            eosEnviado = true
                        } else {
                            input.put(buf, 0, read)
                            val frames = read / 2
                            codec.queueInputBuffer(idx, 0, read, presentationUs, 0)
                            presentationUs += (frames * 1_000_000L) / sampleRate
                        }
                    }
                }
                val info = MediaCodec.BufferInfo()
                val outIdx = codec.dequeueOutputBuffer(info, 10_000)
                if (outIdx >= 0) {
                    if (info.flags and MediaCodec.BUFFER_FLAG_CODEC_CONFIG != 0) {
                        codec.releaseOutputBuffer(outIdx, false)
                        continue
                    }
                    if (muxer == null) {
                        muxer = MediaMuxer(outPath,
                            MediaMuxer.OutputFormat.MUXER_OUTPUT_MPEG_4)
                        track = muxer!!.addTrack(codec.outputFormat)
                        muxer!!.start()
                        muxerStarted = true
                    }
                    val out = codec.getOutputBuffer(outIdx)!!
                    if (info.size > 0 && muxerStarted) {
                        out.position(info.offset)
                        out.limit(info.offset + info.size)
                        muxer!!.writeSampleData(track, out, info)
                    }
                    codec.releaseOutputBuffer(outIdx, false)
                    if (info.flags and MediaCodec.BUFFER_FLAG_END_OF_STREAM != 0) break
                } else if (outIdx == MediaCodec.INFO_OUTPUT_FORMAT_CHANGED) {
                    if (muxer == null) {
                        muxer = MediaMuxer(outPath,
                            MediaMuxer.OutputFormat.MUXER_OUTPUT_MPEG_4)
                        track = muxer!!.addTrack(codec.outputFormat)
                        muxer!!.start()
                        muxerStarted = true
                    }
                }
                if (eosEnviado && outIdx < 0) {
                    // Sin más salida y con EOS enviado: salir si el muxer arrancó.
                    if (muxerStarted) {
                        // Dar una última oportunidad de drenar.
                        Thread.sleep(50)
                    }
                }
            }
        } finally {
            try { fis.close() } catch (_: Exception) {}
            try { codec.stop(); codec.release() } catch (_: Exception) {}
            try {
                if (muxerStarted) {
                    muxer?.stop()
                    muxer?.release()
                }
            } catch (_: Exception) {}
        }
        if (!File(outPath).exists() || File(outPath).length() < 1000) {
            throw IllegalStateException("compressToAac: salida inválida")
        }
    }
}
