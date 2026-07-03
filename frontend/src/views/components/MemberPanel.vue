<template>
  <section class="glass panel">
    <div class="toolbar">
      <input class="input" style="max-width:320px" v-model="kw" placeholder="搜索姓名/学号/性别/专业/方向" @keyup.enter="load">
      <div><button class="btn ghost" @click="refresh">刷新</button> <button class="btn" @click="openAdd">新增成员</button></div>
    </div>
    <table class="table">
      <thead><tr><th>姓名</th><th>学号</th><th>性别</th><th>年级</th><th>专业</th><th>方向</th><th>人脸照片</th><th>操作</th></tr></thead>
      <tbody>
        <tr v-for="m in list" :key="m.id">
          <td>{{m.name}}</td><td>{{m.student_no}}</td><td>{{m.gender}}</td><td>{{m.grade}}</td><td>{{m.major}}</td><td>{{m.direction}}</td><td>{{m.face_photo||'未上传'}}</td>
          <td class="actions"><button class="btn ghost" @click="edit(m)">编辑</button><button class="btn ghost" @click="pickFace(m)">上传人脸</button><button class="btn danger" @click="remove(m)">删除</button></td>
        </tr>
        <tr v-if="!list.length"><td colspan="8" class="empty">暂无成员数据</td></tr>
      </tbody>
    </table>
    <input ref="file" type="file" accept="image/*" hidden @change="uploadFace">
    <p class="err" v-if="err">{{err}}</p>
  </section>
  <div class="modal-mask" v-if="show">
    <div class="glass modal">
      <h2>{{form.id?'编辑成员':'新增成员'}}</h2>
      <div class="form-grid">
        <input class="input" v-model.trim="form.name" placeholder="姓名，必填">
        <input class="input" v-model.trim="form.student_no" placeholder="学号，必填">
        <select class="input" v-model="form.gender"><option value="男">男</option><option value="女">女</option><option value="其他">其他</option></select>
        <input class="input" v-model.trim="form.grade" placeholder="年级，如2024级">
        <input class="input" v-model.trim="form.major" placeholder="专业">
        <input class="input" v-model.trim="form.direction" :disabled="!superMode" placeholder="方向，必填">
        <input class="input" v-model.trim="form.phone" placeholder="电话">
        <input class="input" v-model.trim="form.email" placeholder="邮箱">
        <input class="input" v-model.trim="form.remark" placeholder="备注">
      </div>
      <p class="hint" v-if="!superMode">管理员新增/修改时方向固定为：{{user.direction}}</p>
      <div style="margin-top:16px;text-align:right"><button class="btn ghost" @click="show=false">取消</button> <button class="btn" @click="save">保存</button></div>
      <p class="err" v-if="err">{{err}}</p>
    </div>
  </div>
</template>
<script setup>
import { ref,onMounted } from 'vue'
import http from '../../api/http'
const props=defineProps({superMode:{type:Boolean,default:false}})
const emit=defineEmits(['changed'])
const user=JSON.parse(localStorage.getItem('user')||'{}')
const list=ref([]),kw=ref(''),show=ref(false),err=ref(''),file=ref(null),current=ref(null)
const blank={name:'',student_no:'',gender:'男',grade:'',major:'',direction:user.direction||'',phone:'',email:'',remark:''}
const form=ref({...blank})
async function load(){err.value='';try{list.value=await http.get('/members',{params:{keyword:kw.value}})}catch(e){err.value=e.message}}
async function refresh(){await load();emit('changed')}
function openAdd(){form.value={...blank,direction:props.superMode?'':user.direction};show.value=true;err.value=''}
function edit(m){form.value={...m};show.value=true;err.value=''}
async function save(){
  try{
    const data={...form.value}
    if(!data.name||!data.student_no||!data.gender||!data.direction){err.value='姓名、学号、性别、方向不能为空';return}
    if(!props.superMode)data.direction=user.direction
    if(data.id) await http.put('/members/'+data.id,data)
    else await http.post('/members',data)
    show.value=false;await load();emit('changed')
  }catch(e){err.value=e.message}
}
async function remove(m){if(!confirm('确认删除成员 '+m.name+'？'))return;try{await http.delete('/members/'+m.id);await load();emit('changed')}catch(e){err.value=e.message}}
function pickFace(m){current.value=m;file.value.click()}
async function uploadFace(e){const f=e.target.files[0];if(!f||!current.value)return;const fd=new FormData();fd.append('photo',f);try{await http.post('/members/'+current.value.id+'/face',fd,{headers:{'Content-Type':'multipart/form-data'}});await load()}catch(ex){err.value=ex.message}e.target.value=''}
onMounted(load)
</script>
