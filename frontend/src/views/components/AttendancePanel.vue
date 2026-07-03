<template>
  <section class="glass panel">
    <div class="toolbar">
      <div>
        <h2>签到记录</h2>
        <p class="hint">超级管理员可看全部签到；普通管理员只看自己方向签到。可多选删除测试签到记录。</p>
      </div>
      <div class="toolbar-right">
        <input class="input" style="max-width:260px" v-model="kw" placeholder="搜索姓名/学号/方向/状态" @keyup.enter="load">
        <button class="btn ghost" @click="refresh">刷新</button>
        <button class="btn ghost" @click="openSign">手动签到</button>
        <button class="btn danger" :disabled="!selectedIds.length" @click="batchDelete">
          删除选中<span v-if="selectedIds.length">({{ selectedIds.length }})</span>
        </button>
        <button class="btn" @click="exportCsv">导出表格</button>
      </div>
    </div>

    <table class="table">
      <thead>
        <tr>
          <th style="width:48px">
            <input type="checkbox" :checked="allChecked" :disabled="!rows.length" @change="toggleAll($event)">
          </th>
          <th>姓名</th>
          <th>学号</th>
          <th>性别</th>
          <th>方向</th>
          <th>日期</th>
          <th>时间</th>
          <th>状态</th>
          <th>来源</th>
          <th>备注</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="a in rows" :key="a.id">
          <td><input type="checkbox" :value="a.id" v-model="selectedIds"></td>
          <td>{{a.name}}</td>
          <td>{{a.student_no}}</td>
          <td>{{a.gender}}</td>
          <td>{{a.direction}}</td>
          <td>{{a.check_date}}</td>
          <td>{{a.check_time}}</td>
          <td>{{a.status}}</td>
          <td>{{a.source}}</td>
          <td>{{a.remark}}</td>
          <td class="actions">
            <button class="btn danger" @click="deleteOne(a)">删除</button>
          </td>
        </tr>
        <tr v-if="!rows.length"><td colspan="11" class="empty">暂无签到记录</td></tr>
      </tbody>
    </table>

    <p class="ok" v-if="msg">{{msg}}</p>
    <p class="err" v-if="err">{{err}}</p>
  </section>

  <div class="modal-mask" v-if="show">
    <div class="glass modal">
      <h2>手动签到</h2>
      <div class="form-grid">
        <select class="input" v-model="form.member_id">
          <option value="">选择成员</option>
          <option v-for="m in members" :value="m.id" :key="m.id">{{m.name}} / {{m.student_no}} / {{m.direction}}</option>
        </select>
        <select class="input" v-model="form.status"><option>正常</option><option>迟到</option><option>缺勤</option><option>请假</option></select>
        <input class="input" v-model.trim="form.remark" placeholder="备注">
      </div>
      <div style="margin-top:16px;text-align:right"><button class="btn ghost" @click="show=false">取消</button> <button class="btn" @click="save">保存签到</button></div>
      <p class="err" v-if="err">{{err}}</p>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, onMounted } from 'vue'
import http from '../../api/http'

const emit = defineEmits(['changed'])
const rows = ref([])
const members = ref([])
const kw = ref('')
const err = ref('')
const msg = ref('')
const show = ref(false)
const selectedIds = ref([])
const form = ref({ member_id: '', status: '正常', remark: '' })

const allChecked = computed(() => rows.value.length > 0 && selectedIds.value.length === rows.value.length)

async function load() {
  err.value = ''
  msg.value = ''
  try {
    rows.value = await http.get('/attendance', { params: { keyword: kw.value } })
    selectedIds.value = selectedIds.value.filter(id => rows.value.some(a => a.id === id))
  } catch (e) {
    err.value = e.message
  }
}

async function refresh() {
  await load()
  emit('changed')
}

async function loadMembers() {
  try {
    members.value = await http.get('/members')
  } catch (e) {
    err.value = e.message
  }
}

async function openSign() {
  await loadMembers()
  form.value = { member_id: '', status: '正常', remark: '' }
  show.value = true
  err.value = ''
}

async function save() {
  try {
    if (!form.value.member_id) {
      err.value = '请选择成员'
      return
    }
    await http.post('/attendance', { ...form.value, member_id: Number(form.value.member_id), source: '手动录入' })
    show.value = false
    await load()
    emit('changed')
  } catch (e) {
    err.value = e.message
  }
}

function toggleAll(e) {
  selectedIds.value = e.target.checked ? rows.value.map(a => a.id) : []
}

async function deleteOne(a) {
  err.value = ''
  msg.value = ''
  if (!confirm(`确定删除 ${a.name} 在 ${a.check_date} ${a.check_time} 的签到记录吗？`)) return
  try {
    const res = await http.delete(`/attendance/${a.id}`)
    msg.value = res.message || '删除成功'
    selectedIds.value = selectedIds.value.filter(id => id !== a.id)
    await load()
    emit('changed')
  } catch (e) {
    err.value = e.message
  }
}

async function batchDelete() {
  err.value = ''
  msg.value = ''
  if (!selectedIds.value.length) {
    err.value = '请先勾选要删除的签到记录'
    return
  }
  if (!confirm(`确定删除选中的 ${selectedIds.value.length} 条签到记录吗？`)) return
  try {
    const res = await http.post('/attendance/batch-delete', { ids: selectedIds.value })
    msg.value = res.message || '批量删除成功'
    selectedIds.value = []
    await load()
    emit('changed')
  } catch (e) {
    err.value = e.message
  }
}

function exportCsv() {
  const token = localStorage.getItem('token') || ''
  fetch('/api/attendance/export?keyword=' + encodeURIComponent(kw.value), { headers: { Authorization: 'Bearer ' + token } })
    .then(r => { if (!r.ok) throw new Error('导出失败'); return r.blob() })
    .then(blob => { const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'NBA-Lab签到记录.csv'; a.click(); URL.revokeObjectURL(a.href) })
    .catch(e => err.value = e.message)
}

onMounted(load)
</script>
