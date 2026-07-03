<template>
  <section class="glass panel">
    <div class="toolbar">
      <h2>管理员账号设置</h2>
      <button class="btn" @click="openAdd">新增管理员</button>
    </div>
    <p class="hint">新增管理员时必须设置登录账号、登录密码、姓名和负责方向。管理员登录后只能管理自己方向的数据。</p>
    <table class="table">
      <thead><tr><th>账号</th><th>姓名</th><th>角色</th><th>负责方向</th><th>状态</th><th>操作</th></tr></thead>
      <tbody>
        <tr v-for="u in users" :key="u.id">
          <td>{{u.username}}</td><td>{{u.real_name}}</td><td>{{roleText(u.role)}}</td><td>{{u.direction||'-'}}</td><td>{{statusText(u.status)}}</td>
          <td class="actions"><button class="btn ghost" @click="edit(u)">编辑</button><button class="btn danger" @click="del(u)">删除</button></td>
        </tr>
      </tbody>
    </table>
    <p class="err" v-if="err">{{err}}</p>
  </section>
  <div class="modal-mask" v-if="show">
    <div class="glass modal">
      <h2>{{form.id?'编辑管理员':'新增管理员'}}</h2>
      <div class="form-grid">
        <input class="input" v-model.trim="form.username" :disabled="!!form.id" placeholder="登录账号，如 dladmin">
        <input class="input" v-model.trim="form.password" type="password" :placeholder="form.id?'新密码，留空不修改':'登录密码，必填'">
        <input class="input" v-model.trim="form.real_name" placeholder="姓名">
        <input class="input" v-model.trim="form.direction" placeholder="负责方向，如 深度学习方向">
        <select class="input" v-model="form.status"><option value="enabled">启用</option><option value="disabled">禁用</option></select>
      </div>
      <div style="margin-top:16px;text-align:right"><button class="btn ghost" @click="show=false">取消</button> <button class="btn" @click="save">保存</button></div>
      <p class="err" v-if="err">{{err}}</p>
    </div>
  </div>
</template>
<script setup>
import { ref,onMounted } from 'vue'
import http from '../../api/http'
const emit=defineEmits(['changed'])
const users=ref([]),show=ref(false),err=ref('')
const form=ref({})
function roleText(r){return r==='super_admin'?'超级管理员':'管理员'}
function statusText(s){return s==='enabled'?'启用':'禁用'}
async function load(){err.value='';try{users.value=await http.get('/users')}catch(e){err.value=e.message}}
function openAdd(){form.value={username:'',password:'',real_name:'',role:'admin',direction:'',status:'enabled'};show.value=true;err.value=''}
function edit(u){form.value={...u,password:''};show.value=true;err.value=''}
async function save(){
  try{
    if(!form.value.username||!form.value.real_name||!form.value.direction){err.value='账号、姓名、负责方向不能为空';return}
    if(!form.value.id && !form.value.password){err.value='新增管理员必须设置登录密码';return}
    const data={...form.value,role:'admin'}
    if(data.id){if(!data.password)delete data.password;await http.put('/users/'+data.id,data)}
    else await http.post('/users',data)
    show.value=false;await load();emit('changed')
  }catch(e){err.value=e.message}
}
async function del(u){if(!confirm('确认删除 '+u.username+'？'))return;try{await http.delete('/users/'+u.id);await load();emit('changed')}catch(e){err.value=e.message}}
onMounted(load)
</script>
