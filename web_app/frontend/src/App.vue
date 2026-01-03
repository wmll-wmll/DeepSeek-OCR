<script setup>
import { ref, computed } from 'vue'
import { UploadFilled, Document, Reading, Picture } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import { marked } from 'marked'

const uploadUrl = ref('')
const fileList = ref([])
const selectedMode = ref('markdown')
const loading = ref(false)
const result = ref('')
const rawResult = ref('')
const activeResultTab = ref('preview')

const imageUrl = computed(() => {
  if (fileList.value.length > 0 && fileList.value[0].raw) {
    return URL.createObjectURL(fileList.value[0].raw)
  }
  return ''
})

const renderedMarkdown = computed(() => {
  return marked(result.value)
})

const handleUploadChange = (file) => {
  fileList.value = [file]
  result.value = ''
  rawResult.value = ''
}

const handleRemove = () => {
  fileList.value = []
  result.value = ''
  rawResult.value = ''
}

const submitUpload = async () => {
  if (fileList.value.length === 0) {
    ElMessage.warning('请先选择一张图片')
    return
  }

  loading.value = true
  const formData = new FormData()
  formData.append('file', fileList.value[0].raw)
  formData.append('mode', selectedMode.value)

  try {
    const response = await axios.post('/api/ocr', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
    
    if (response.data && response.data.result) {
      result.value = response.data.result
      rawResult.value = response.data.result
      ElMessage.success('识别成功')
    } else {
      ElMessage.warning('未返回识别结果')
    }
  } catch (error) {
    console.error(error)
    ElMessage.error('识别失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    loading.value = false
  }
}

const copyResult = () => {
  if (!rawResult.value) return
  navigator.clipboard.writeText(rawResult.value).then(() => {
    ElMessage.success('复制成功')
  }).catch(() => {
    ElMessage.error('复制失败')
  })
}
</script>

<template>
  <el-container class="layout-container">
    <el-header class="header">
      <div class="logo">
        <el-icon :size="30" style="margin-right: 10px; vertical-align: middle;"><Reading /></el-icon>
        <span style="font-size: 20px; font-weight: bold; vertical-align: middle;">DeepSeek-OCR Web</span>
      </div>
    </el-header>

    <el-main>
      <el-row :gutter="20">
        <!-- 左侧：上传与预览 -->
        <el-col :span="10">
          <el-card class="box-card" shadow="hover">
            <template #header>
              <div class="card-header">
                <span><el-icon><Picture /></el-icon> 图片上传</span>
              </div>
            </template>
            
            <div class="upload-area">
              <el-upload
                class="upload-demo"
                drag
                action="#"
                :auto-upload="false"
                :on-change="handleUploadChange"
                :on-remove="handleRemove"
                :file-list="fileList"
                :limit="1"
                accept="image/*"
                list-type="picture"
              >
                <el-icon class="el-icon--upload"><upload-filled /></el-icon>
                <div class="el-upload__text">
                  拖拽文件到此处或 <em>点击上传</em>
                </div>
                <template #tip>
                  <div class="el-upload__tip">
                    只能上传 jpg/png 文件
                  </div>
                </template>
              </el-upload>
            </div>

            <el-divider />

            <div class="controls">
              <div style="margin-bottom: 15px;">
                <span style="margin-right: 10px; font-weight: bold;">识别模式:</span>
                <el-radio-group v-model="selectedMode">
                  <el-radio label="markdown" border>Markdown 格式化</el-radio>
                  <el-radio label="ocr" border>纯文本 OCR</el-radio>
                </el-radio-group>
              </div>
              
              <el-button type="primary" size="large" @click="submitUpload" :loading="loading" style="width: 100%;">
                开始识别
              </el-button>
            </div>
          </el-card>
        </el-col>

        <!-- 右侧：结果展示 -->
        <el-col :span="14">
          <el-card class="box-card result-card" shadow="hover">
            <template #header>
              <div class="card-header">
                <span><el-icon><Document /></el-icon> 识别结果</span>
                <el-button v-if="rawResult" size="small" @click="copyResult">复制结果</el-button>
              </div>
            </template>
            
            <el-tabs v-model="activeResultTab" type="border-card">
              <el-tab-pane label="预览效果" name="preview">
                <div v-if="loading" class="loading-state">
                  <el-skeleton :rows="10" animated />
                </div>
                <div v-else-if="result" class="markdown-body" v-html="renderedMarkdown"></div>
                <div v-else class="empty-state">
                  暂无结果
                </div>
              </el-tab-pane>
              <el-tab-pane label="原始内容" name="raw">
                <el-input
                  v-model="rawResult"
                  type="textarea"
                  :rows="20"
                  readonly
                  placeholder="识别结果将显示在这里..."
                />
              </el-tab-pane>
            </el-tabs>
          </el-card>
        </el-col>
      </el-row>
    </el-main>
  </el-container>
</template>

<style scoped>
.layout-container {
  height: 100vh;
  background-color: #f5f7fa;
}

.header {
  background-color: #fff;
  border-bottom: 1px solid #dcdfe6;
  display: flex;
  align-items: center;
  padding: 0 20px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
}

.logo {
  color: #409eff;
}

.el-main {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: bold;
}

.upload-area {
  text-align: center;
}

.result-card {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.result-card :deep(.el-card__body) {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden; 
}

.el-tabs {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.el-tabs :deep(.el-tabs__content) {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.markdown-body {
  text-align: left;
  line-height: 1.6;
}

.empty-state {
  color: #909399;
  text-align: center;
  padding-top: 50px;
}

.loading-state {
  padding: 20px;
}
</style>
