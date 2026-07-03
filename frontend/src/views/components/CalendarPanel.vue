<template>
  <section class="glass panel calendar-panel">
    <div class="calendar-head">
      <div>
        <h2>培训 / 比赛日历</h2>
        <p class="hint">点击日期添加日程；跨多天的比赛会在周视图中横向铺开。不同方向时间冲突时后端会拦截并提示换时间。</p>
      </div>
      <div class="calendar-tools">
        <button class="btn ghost" @click="prevMonth">上个月</button>
        <strong>{{ year }}年{{ month + 1 }}月</strong>
        <button class="btn ghost" @click="nextMonth">下个月</button>
        <button class="btn" @click="openAdd()">新增日程</button>
      </div>
    </div>

    <div class="calendar-week-title">
      <div v-for="d in weekNames" :key="d">{{ d }}</div>
    </div>

    <div class="month-board">
      <div v-for="(week, wi) in weeks" :key="wi" class="week-row">
        <div class="day-grid">
          <div
            v-for="day in week.days"
            :key="day.date"
            class="day-cell"
            :class="{ muted: !day.current, today: day.date === today }"
            @click="openAdd(day.date)"
          >
            <span>{{ day.day }}</span>
          </div>
        </div>

        <div class="event-layer">
          <div
            v-for="bar in week.bars"
            :key="bar.id + '-' + bar.startCol + '-' + wi"
            class="event-bar"
            :style="{ gridColumn: bar.startCol + ' / span ' + bar.span, gridRow: bar.row }"
            :title="bar.title"
            @click.stop="edit(bar.raw)"
          >
            {{ bar.direction }}｜{{ bar.timeText }}｜{{ bar.title }}
          </div>
        </div>
      </div>
    </div>

    <p class="err" v-if="err">{{ err }}</p>
  </section>

  <div class="modal-mask" v-if="show">
    <div class="glass modal">
      <h2>{{ form.id ? '编辑日程' : '新增日程' }}</h2>
      <div class="form-grid">
        <input class="input" v-model.trim="form.title" placeholder="日程名称，如算法培训 / 省赛集训">
        <input class="input" v-model.trim="form.direction" :disabled="!superMode" placeholder="方向">
        <label class="field mini"><span>开始日期</span><input class="input" type="date" v-model="form.start_date"></label>
        <label class="field mini"><span>结束日期</span><input class="input" type="date" v-model="form.end_date"></label>
        <label class="field mini"><span>开始时间</span><input class="input" type="time" v-model="form.start_time"></label>
        <label class="field mini"><span>结束时间</span><input class="input" type="time" v-model="form.end_time"></label>
        <input class="input wide" v-model.trim="form.description" placeholder="备注，可不填">
      </div>
      <p class="hint" v-if="!superMode">方向管理员只能添加/修改自己方向：{{ user.direction }}</p>
      <div class="modal-actions">
        <button class="btn danger" v-if="form.id" @click="remove">删除</button>
        <span></span>
        <button class="btn ghost" @click="show=false">取消</button>
        <button class="btn" @click="save">确定</button>
      </div>
      <p class="err" v-if="err">{{ err }}</p>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import http from '../../api/http'

const props = defineProps({ superMode: { type: Boolean, default: false } })
const emit = defineEmits(['changed'])
const user = JSON.parse(localStorage.getItem('user') || '{}')
const now = new Date()
const viewDate = ref(new Date(now.getFullYear(), now.getMonth(), 1))
const plans = ref([])
const show = ref(false)
const err = ref('')
const today = toDateText(now)
const weekNames = ['一','二','三','四','五','六','日']

const blank = {
  title: '',
  direction: user.direction || '',
  start_date: today,
  end_date: today,
  start_time: '19:00',
  end_time: '21:00',
  description: ''
}
const form = ref({ ...blank })

const year = computed(() => viewDate.value.getFullYear())
const month = computed(() => viewDate.value.getMonth())

function toDateText(d){
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}
function parseDate(text){
  const [y,m,d] = text.split('-').map(Number)
  return new Date(y, m - 1, d)
}
function addDays(d, n){
  const x = new Date(d)
  x.setDate(x.getDate() + n)
  return x
}
function mondayOf(d){
  const x = new Date(d)
  const day = x.getDay() || 7
  x.setDate(x.getDate() - day + 1)
  return x
}
function overlap(a1, a2, b1, b2){
  return a1 <= b2 && a2 >= b1
}
function sameMonth(d){
  return d.getFullYear() === year.value && d.getMonth() === month.value
}

const range = computed(() => {
  const first = new Date(year.value, month.value, 1)
  const last = new Date(year.value, month.value + 1, 0)
  return { start: toDateText(mondayOf(first)), end: toDateText(addDays(mondayOf(last), 6)) }
})

const weeks = computed(() => {
  const firstMonday = parseDate(range.value.start)
  const out = []
  for(let w = 0; w < 6; w++){
    const ws = addDays(firstMonday, w * 7)
    const we = addDays(ws, 6)
    const days = []
    for(let i = 0; i < 7; i++){
      const d = addDays(ws, i)
      days.push({ date: toDateText(d), day: d.getDate(), current: sameMonth(d) })
    }
    const bars = plans.value
      .filter(p => overlap(parseDate(p.start_date), parseDate(p.end_date), ws, we))
      .map((p, idx) => {
        const s = parseDate(p.start_date) < ws ? ws : parseDate(p.start_date)
        const e = parseDate(p.end_date) > we ? we : parseDate(p.end_date)
        const startCol = Math.floor((s - ws) / 86400000) + 1
        const span = Math.floor((e - s) / 86400000) + 1
        return {
          id: p.id,
          raw: p,
          title: p.title,
          direction: p.direction,
          timeText: `${p.start_time}-${p.end_time}`,
          startCol,
          span,
          row: idx + 1
        }
      })
    out.push({ days, bars })
  }
  return out
})

async function load(){
  err.value = ''
  try{
    plans.value = await http.get('/training-plans', { params: range.value })
  }catch(e){ err.value = e.message }
}
function prevMonth(){ viewDate.value = new Date(year.value, month.value - 1, 1); load() }
function nextMonth(){ viewDate.value = new Date(year.value, month.value + 1, 1); load() }
function openAdd(date){
  form.value = { ...blank, direction: props.superMode ? '' : user.direction, start_date: date || today, end_date: date || today }
  show.value = true
  err.value = ''
}
function edit(p){
  form.value = { ...p }
  show.value = true
  err.value = ''
}
async function save(){
  try{
    const data = { ...form.value }
    if(!props.superMode) data.direction = user.direction
    if(!data.title || !data.direction || !data.start_date || !data.end_date || !data.start_time || !data.end_time){
      err.value = '日程名称、方向、日期和时间不能为空'
      return
    }
    if(data.id) await http.put('/training-plans/' + data.id, data)
    else await http.post('/training-plans', data)
    show.value = false
    await load()
    emit('changed')
  }catch(e){ err.value = e.message }
}
async function remove(){
  if(!confirm('确认删除这个日程？')) return
  try{
    await http.delete('/training-plans/' + form.value.id)
    show.value = false
    await load()
    emit('changed')
  }catch(e){ err.value = e.message }
}

onMounted(load)
</script>
