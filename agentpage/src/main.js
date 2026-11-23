import '@/styles/common.css'

import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { filePickerPlugin } from '@/directives'

import App from './App.vue'
import router from './router'

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.use(filePickerPlugin)

app.mount('#app')
