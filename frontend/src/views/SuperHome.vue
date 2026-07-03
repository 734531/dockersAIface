<template>
  <div class="page layout">
    <aside class="side">
      <div class="brand">NBA-Lab</div>
      <p class="sub">超级管理员控制台</p>
      <div class="nav">
        <button class="btn ghost" :class="{active:tab==='members'}" @click="tab='members'">全体成员管理</button>
        <button class="btn ghost" :class="{active:tab==='admins'}" @click="tab='admins'">管理员设置</button>
        <button class="btn ghost" :class="{active:tab==='attendance'}" @click="tab='attendance'">签到记录</button>
        <button class="btn ghost" :class="{active:tab==='calendar'}" @click="tab='calendar'">培训比赛日历</button>
        <button class="btn ghost" :class="{active:tab==='camera'}" @click="tab='camera'">摄像头配置</button>
        <button class="btn danger" @click="logout">退出登录</button>
      </div>
    </aside>

    <main class="main">
      <div class="top">
        <h1>NBA-Lab实验室</h1>
        <span>{{user.real_name}} / SUPER</span>
      </div>

      <div class="cards">
        <div class="glass card"><div>成员总数</div><div class="num">{{stats.members ?? 0}}</div></div>
        <div class="glass card"><div>管理员数</div><div class="num">{{stats.admins ?? 0}}</div></div>
        <div class="glass card"><div>签到记录</div><div class="num">{{stats.attendance ?? 0}}</div></div>
      </div>

      <MemberPanel v-if="tab==='members'" super-mode @changed="load" />
      <AdminPanel v-if="tab==='admins'" @changed="load" />
      <AttendancePanel v-if="tab==='attendance'" super-mode @changed="load" />
      <CalendarPanel v-if="tab==='calendar'" super-mode @changed="load" />
      <CameraPanel v-if="tab==='camera'" />
    </main>
  </div>
</template>
<script setup>
import { ref,onMounted } from 'vue'
import { useRouter } from 'vue-router'
import http from '../api/http'
import MemberPanel from './components/MemberPanel.vue'
import AdminPanel from './components/AdminPanel.vue'
import CameraPanel from './components/CameraPanel.vue'
import AttendancePanel from './components/AttendancePanel.vue'
import CalendarPanel from './components/CalendarPanel.vue'
const router=useRouter()
const user=ref(JSON.parse(localStorage.getItem('user')||'{}'))
const tab=ref('members')
const stats=ref({})
async function load(){ try{ const me=await http.get('/auth/me'); user.value=me; localStorage.setItem('user', JSON.stringify(me)); stats.value=await http.get('/stats') }catch(e){} }
function logout(){localStorage.clear();router.push('/login')}
onMounted(load)
</script>
