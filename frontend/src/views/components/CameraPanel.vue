<template>
  <section class="glass panel">
    <h2>摄像头配置</h2>
    <p class="hint">测试阶段保持“测试模式”，不连接内网摄像头也能正常登录、管理成员和上传人脸照片。正式接海康威视摄像头时，建议 RTSP 使用：rtsp://用户名:密码@摄像头IP:554/Streaming/Channels/101。</p>

    <div class="form-grid">
      <input class="input" v-model="c.camera_name" placeholder="摄像头名称">
      <input class="input" v-model="c.rtsp_url" placeholder="rtsp://用户名:密码@摄像头IP:554/Streaming/Channels/101">
      <input class="input" v-model="c.username" placeholder="海康威视摄像头用户名">
      <input class="input" v-model="c.password" type="password" placeholder="海康威视摄像头密码">
      <select v-model="c.enabled">
        <option :value="false">停用摄像头</option>
        <option :value="true">启用摄像头</option>
      </select>
      <select v-model="c.test_mode">
        <option :value="true">测试模式：不连摄像头</option>
        <option :value="false">正式模式：连接摄像头</option>
      </select>
    </div>

    <div class="camera-tips">
      <b>海康威视常用地址：</b>
      <span>主码流：rtsp://用户名:密码@IP:554/Streaming/Channels/101</span>
      <span>子码流：rtsp://用户名:密码@IP:554/Streaming/Channels/102</span>
      <span>如果 RTSP 地址里不写用户名密码，后端会自动使用下面填写的用户名和密码拼接。</span>
      <span>当前已预置：IP 192.168.1.111，用户名 admin，主码流 101。</span>
    </div>

    <div style="margin-top:16px;display:flex;gap:12px;flex-wrap:wrap">
      <button class="btn" @click="save">保存配置</button>
      <button class="btn ghost" @click="testConnect">OpenCV测试连接</button>
      <button class="btn ghost" @click="snapshot">抓拍一帧</button>
      <button class="btn" @click="recognizeSign">识别并自动签到</button>
    </div>

    <p class="ok" v-if="msg">{{ msg }}</p>
    <p class="err" v-if="err">{{ err }}</p>
    <div class="glass camera-result" v-if="result">
      <div>状态：{{ result.ok ? '连接成功' : '连接失败' }}</div>
      <div v-if="result.width">画面：{{ result.width }} × {{ result.height }}，FPS：{{ result.fps }}</div>
      <div v-if="result.rtsp_url">RTSP：{{ result.rtsp_url }}</div>
      <div v-if="result.filename">抓拍文件：backend/faces/_snapshots/{{ result.filename }}</div>
    </div>
  </section>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import http from '../../api/http'

const c = ref({
  camera_name: 'NBA-Lab Hikvision Camera',
  rtsp_url: 'rtsp://192.168.1.111:554/Streaming/Channels/101',
  username: 'admin',
  password: '',
  enabled: true,
  test_mode: false
})

const msg = ref('')
const err = ref('')
const result = ref(null)
let noticeTimer = null

function showNotice(type, text, keep = false) {
  if (noticeTimer) clearTimeout(noticeTimer)

  if (type === 'success') {
    msg.value = text
    err.value = ''
  } else {
    err.value = text
    msg.value = ''
  }

  if (!keep) {
    noticeTimer = setTimeout(() => {
      msg.value = ''
      err.value = ''
      noticeTimer = null
    }, 2500)
  }
}

async function load() {
  try {
    c.value = await http.get('/camera')
  } catch (e) {
    showNotice('error', e.message || '摄像头配置加载失败')
  }
}

async function save() {
  try {
    await http.put('/camera', c.value)
    showNotice('success', '保存成功')
  } catch (e) {
    showNotice('error', e.message || '保存失败')
  }
}

async function testConnect() {
  result.value = null
  try {
    await http.put('/camera', c.value)
    showNotice('success', '正在通过 OpenCV 连接摄像头，请稍等...', true)
    const res = await http.post('/camera/test-connect')
    result.value = res
    showNotice(res.ok ? 'success' : 'error', res.message || '检测完成', true)
  } catch (e) {
    showNotice('error', e.message || '摄像头连接测试失败', true)
  }
}

async function snapshot() {
  result.value = null
  try {
    await http.put('/camera', c.value)
    showNotice('success', '正在抓拍，请稍等...', true)
    const res = await http.post('/camera/snapshot')
    result.value = res
    showNotice(res.ok ? 'success' : 'error', res.message || '抓拍完成', true)
  } catch (e) {
    showNotice('error', e.message || '抓拍失败', true)
  }
}

async function recognizeSign() {
  result.value = null
  try {
    await http.put('/camera', c.value)
    showNotice('success', '正在识别人脸并自动签到，请正对摄像头...', true)
    const res = await http.post('/face/recognize-and-sign')
    result.value = res
    showNotice(res.ok ? 'success' : 'error', res.message || '识别完成', true)
  } catch (e) {
    showNotice('error', e.message || '识别签到失败', true)
  }
}

onMounted(load)
</script>
