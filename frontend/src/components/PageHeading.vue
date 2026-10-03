<script setup lang="ts">defineProps<{ title: string; description: string }>()</script>
<template><div class="page-heading"><div><h1>{{ title }}</h1><p>{{ description }}</p></div><slot /></div></template>
