<template>
  <div class="page layout">
    <aside class="side">
      <div class="brand">NBA-Lab</div>
      <p class="sub">方向管理员工作台</p>

      <div class="nav">
        <button
          class="btn ghost"
          :class="{active:tab==='members'}"
          @click="tab='members'"
        >
          {{ user.direction }} 成员管理
        </button>

        <button
          class="btn ghost"
          :class="{active:tab==='attendance'}"
          @click="tab='attendance'"
        >
          本方向签到记录
        </button>

        <button
          class="btn ghost"
          :class="{active:tab==='calendar'}"
          @click="tab='calendar'"
        >
          培训比赛日历
        </button>

        <button class="btn ghost" @click="testFace">
          接口自检
        </button>

        <button class="btn danger" @click="logout">
          退出登录
        </button>
      </div>
    </aside>

    <main class="main">
      <div class="top">
        <h1>{{ user.direction }} 管理首页</h1>
        <span>{{ user.real_name }} / ADMIN</span>
      </div>

      <div class="cards">

        <div class="glass card">
          <div>本方向成员</div>
          <div class="num">
            {{ stats.members ?? 0 }}
          </div>
        </div>

        <div class="glass card">
          <div>签到记录</div>
          <div class="num">
            {{ stats.attendance ?? 0 }}
          </div>
        </div>

        <div class="glass card">
          <div>摄像头状态</div>

          <div
            class="num"
            :style="{
              color:
                cameraStatus==='正常'
                  ? '#4ade80'
                  : cameraStatus==='离线'
                  ? '#ef4444'
                  : '#38bdf8'
            }"
          >
            {{ cameraStatus }}
          </div>
        </div>

      </div>

      <p class="hint">
        管理员只能看到并管理自己方向的成员和签到记录。
      </p>

      <MemberPanel
        v-if="tab==='members'"
        @changed="load"
      />

      <AttendancePanel
        v-if="tab==='attendance'"
        @changed="load"
      />

      <CalendarPanel
        v-if="tab==='calendar'"
        @changed="load"
      />

      <div
        class="toast-mask"
        v-if="toast.show"
        :key="toast.key"
      >
        <div
          class="glass toast-box"
          :class="toast.type"
        >
          <div class="toast-title">
            {{ toast.title }}
          </div>

          <div class="toast-text">
            {{ toast.text }}
          </div>
        </div>
      </div>

    </main>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import http from '../api/http'

import MemberPanel from './components/MemberPanel.vue'
import AttendancePanel from './components/AttendancePanel.vue'
import CalendarPanel from './components/CalendarPanel.vue'

const router = useRouter()

const user = ref(
  JSON.parse(
    localStorage.getItem('user') || '{}'
  )
)

const stats = ref({})
const tab = ref('members')

const cameraStatus = ref('检测中')

const toast = ref({
  show:false,
  type:'success',
  title:'',
  text:'',
  key:0
})

let toastTimer = null
let cameraTimer = null

async function load(){
  try{
    const me = await http.get('/auth/me')

    user.value = me

    localStorage.setItem(
      'user',
      JSON.stringify(me)
    )

    stats.value = await http.get('/stats')

  }catch(e){
    console.error(e)
  }
}

function showToast(type,title,text){

  if(toastTimer){
    clearTimeout(toastTimer)
  }

  toast.value = {
    show:true,
    type,
    title,
    text,
    key:Date.now()
  }

  toastTimer = setTimeout(()=>{
    toast.value.show = false
    toastTimer = null
  },2200)
}

async function testFace(){

  try{

    const r = await http.post('/face/test')

    showToast(
      'success',
      '接口自检成功',
      r.message || '系统接口正常'
    )

    await load()

  }catch(e){

    showToast(
      'error',
      '接口自检失败',
      e.message || '请检查后端服务'
    )
  }
}

async function loadCameraStatus(){

  try{

    const r = await http.post('/face/test')

    if(
      r &&
      (
        r.ok === true ||
        r.success === true
      )
    ){
      cameraStatus.value = '正常'
    }else{
      cameraStatus.value = '异常'
    }

  }catch(e){

    cameraStatus.value = '离线'
  }
}

function logout(){

  localStorage.clear()

  router.push('/login')
}

onMounted(async ()=>{

  await load()

  await loadCameraStatus()

  cameraTimer = setInterval(
    loadCameraStatus,
    10000
  )
})

onUnmounted(()=>{

  if(cameraTimer){
    clearInterval(cameraTimer)
  }

  if(toastTimer){
    clearTimeout(toastTimer)
  }
})
</script>