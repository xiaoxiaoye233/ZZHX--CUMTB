<template>
  <header class="topbar">
    <div class="school-name">中国矿业大学（北京） <span>人工智能学院&amp;理学院</span></div>
    <nav class="navigation" aria-label="页面导航">
      <RouterLink to="/" active-class="nav-active" exact-active-class="nav-active">登录页面</RouterLink>
      <span class="nav-divider">/</span>
      <RouterLink to="/teacher" active-class="nav-active" :class="{ 'nav-active': $route.path.startsWith('/teacher') }">教师端</RouterLink>
      <span class="nav-divider">/</span>
      <RouterLink to="/student" active-class="nav-active" :class="{ 'nav-active': $route.path.startsWith('/student') }">学生端</RouterLink>
    </nav>
  </header>
</template>

<style scoped>
.topbar { min-height: 64px; padding: 0 36px; display: flex; align-items: center; justify-content: space-between; gap: 24px; border: 1px solid rgba(255,255,255,.9); border-radius: 18px; background: linear-gradient(105deg, #f3d6d1 0%, #f9e9e4 44%, #fffdf9 100%); box-shadow: 0 7px 30px rgba(95,67,56,.04); }
.school-name { font-size: 16px; font-weight: 700; letter-spacing: .035em; line-height: 1.7; }
.school-name span { margin-left: 10px; }
.navigation { display: flex; align-items: center; gap: 14px; color: #5b7090; font-size: 14px; white-space: nowrap; }
.nav-active { color: #183e6c; font-weight: 700; }
.nav-divider { color: #c6bec0; }
.navigation a { color: inherit; text-decoration: none; }
.navigation a.nav-active { color: #183e6c; font-weight: 700; }
.navigation a:hover { color: #183e6c; }
@media (max-width: 850px) { .topbar { padding: 20px 24px; flex-wrap: wrap; } }
@media (max-width: 520px) { .topbar { gap: 12px; border-radius: 14px; } .school-name { font-size: 14px; } .school-name span { display: block; margin-left: 0; } .navigation { font-size: 13px; gap: 10px; } }
</style>
