<script setup>
/**
 * CourseDetail.vue 课程详情
 * 内容：视频播放区（占位 + 播放地址获取）、收藏、打分、评论（含回复、点赞、删除）、相关推荐
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'

import PageHeader from '@/components/PageHeader.vue'
import EmptyState from '@/components/EmptyState.vue'
import { useUserStore } from '@/stores/user'
import {
  commentCourse,
  deleteCourseComment,
  favoriteCourse,
  getCourseComments,
  getCourseDetail,
  getCourseRating,
  getCourseVideo,
  getRelatedCourses,
  likeCourseComment,
  rateCourse,
  unfavoriteCourse,
  unlikeCourseComment
} from '@/api/course'
import { resolveAsset } from '@/api/request'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

/** 课程 ID */
const courseId = computed(() => route.params.id)

// ---------------- 课程详情 ----------------
const course = ref(null)
const loading = ref(true)
const errorMsg = ref('')

/** 难度文案 */
const difficultyMap = { 1: '初级', 2: '中级', 3: '高级', 4: '进阶', 5: '极限' }

/** 封面地址 */
const coverUrl = computed(() => resolveAsset(course.value?.cover || ''))

/** 当前登录用户 ID（用于判断能否删除自己的评论） */
const myUserId = computed(() => Number(userStore.user?.id || userStore.profile?.id || 0))

/** 加载课程详情 */
async function loadCourse() {
  loading.value = true
  errorMsg.value = ''
  try {
    course.value = await getCourseDetail(courseId.value)
  } catch (error) {
    course.value = null
    errorMsg.value = '课程加载失败，可能已下架'
  } finally {
    loading.value = false
  }
}

// ---------------- 视频播放 ----------------
const videoInfo = ref(null)
const videoLoading = ref(false)
const videoError = ref('')
/** 是否已经展开播放器（点击播放后才请求播放地址） */
const playerActive = ref(false)

/** 视频地址 */
const videoUrl = computed(() => videoInfo.value?.video_url || '')

/** 是否是可以直接被 <video> 播放的格式（m3u8 需 hls.js，这里只做占位提示） */
const isDirectPlayable = computed(() => /\.(mp4|webm|ogg)(\?|#|$)/i.test(videoUrl.value))

/**
 * 请求播放地址并展开播放器
 * 说明：详情接口不返回 video_url，必须单独调用 /api/courses/{id}/video
 */
async function handlePlay() {
  if (playerActive.value && videoUrl.value) return
  videoLoading.value = true
  videoError.value = ''
  try {
    videoInfo.value = await getCourseVideo(courseId.value)
    playerActive.value = true
    if (!videoInfo.value?.video_url) {
      videoError.value = '该课程暂未上传视频'
    }
  } catch (error) {
    videoError.value = '播放地址获取失败，请稍后重试'
  } finally {
    videoLoading.value = false
  }
}

// ---------------- 收藏 ----------------
const favoriteLoading = ref(false)

/** 切换收藏状态 */
async function handleToggleFavorite() {
  if (!course.value) return
  favoriteLoading.value = true
  try {
    const data = course.value.is_favorited
      ? await unfavoriteCourse(courseId.value)
      : await favoriteCourse(courseId.value)
    course.value.is_favorited = Boolean(data?.is_favorited ?? !course.value.is_favorited)
    if (data?.favorite_count !== undefined) course.value.favorite_count = data.favorite_count
    ElMessage.success(course.value.is_favorited ? '已加入收藏' : '已取消收藏')
  } catch (error) {
    /* 错误已提示 */
  } finally {
    favoriteLoading.value = false
  }
}

// ---------------- 打分 ----------------
const rating = ref({ my_score: null, rating_avg: 0, rating_count: 0 })
const ratingLoading = ref(true)
const ratingSaving = ref(false)
/** 星级组件绑定的值 */
const myScore = ref(0)

/** 加载评分信息 */
async function loadRating() {
  ratingLoading.value = true
  try {
    const data = await getCourseRating(courseId.value)
    rating.value = {
      my_score: data?.my_score ?? null,
      rating_avg: Number(data?.rating_avg ?? 0),
      rating_count: Number(data?.rating_count ?? 0)
    }
    myScore.value = Number(data?.my_score ?? 0)
  } catch (error) {
    // 401 或异常时保持默认值，不影响页面其他功能
    rating.value = { my_score: null, rating_avg: Number(course.value?.rating_avg ?? 0), rating_count: 0 }
  } finally {
    ratingLoading.value = false
  }
}

/** 提交评分 */
async function handleRate(value) {
  const score = Number(value)
  if (!score) {
    ElMessage.warning('请选择 1-5 星评分')
    return
  }
  ratingSaving.value = true
  try {
    const data = await rateCourse(courseId.value, { score })
    rating.value = {
      my_score: data?.my_score ?? score,
      rating_avg: Number(data?.rating_avg ?? rating.value.rating_avg),
      rating_count: Number(data?.rating_count ?? rating.value.rating_count)
    }
    if (course.value) {
      course.value.rating_avg = rating.value.rating_avg
      course.value.rating_count = rating.value.rating_count
    }
    ElMessage.success(`评分成功：${score} 星`)
  } catch (error) {
    /* 错误已提示 */
  } finally {
    ratingSaving.value = false
  }
}

// ---------------- 评论 ----------------
const comments = ref([])
const commentsLoading = ref(true)
const commentsError = ref('')
const commentPage = ref(1)
const commentPageSize = ref(10)
const commentTotal = ref(0)
/** 点赞/删除等操作中的评论 id */
const commentBusy = ref({})

/** 新评论内容 */
const commentForm = reactive({ content: '' })
const commentSubmitting = ref(false)

/** 回复相关状态 */
const replyTarget = ref(null)
const replyContent = ref('')
const replySubmitting = ref(false)

/** 加载评论列表 */
async function loadComments() {
  commentsLoading.value = true
  commentsError.value = ''
  try {
    const data = await getCourseComments(courseId.value, {
      page: commentPage.value,
      page_size: commentPageSize.value
    })
    comments.value = Array.isArray(data) ? data : data?.items || []
    commentTotal.value = Number(data?.total ?? comments.value.length)
  } catch (error) {
    comments.value = []
    commentTotal.value = 0
    commentsError.value = '评论加载失败'
  } finally {
    commentsLoading.value = false
  }
}

/** 评论分页 */
function handleCommentPageChange(nextPage) {
  commentPage.value = nextPage
  loadComments()
}

/** 发表评论（不带 parent_id 即一级评论） */
async function handleSubmitComment() {
  const content = commentForm.content.trim()
  if (content.length < 3) {
    ElMessage.warning('评论内容至少 3 个字')
    return
  }
  if (content.length > 500) {
    ElMessage.warning('评论内容最多 500 个字')
    return
  }
  commentSubmitting.value = true
  try {
    await commentCourse(courseId.value, { content })
    ElMessage.success('评论已提交，审核通过后公开显示')
    commentForm.content = ''
    // 待审核评论不会立刻出现在列表里，这里只刷新统计
    if (course.value) course.value.comment_count = Number(course.value.comment_count || 0) + 1
  } catch (error) {
    /* 错误已提示 */
  } finally {
    commentSubmitting.value = false
  }
}

/** 打开回复框 */
function openReply(comment) {
  replyTarget.value = comment
  replyContent.value = ''
}

/** 取消回复 */
function cancelReply() {
  replyTarget.value = null
  replyContent.value = ''
}

/** 提交回复（parent_id 指向一级评论） */
async function handleSubmitReply() {
  const content = replyContent.value.trim()
  if (content.length < 3) {
    ElMessage.warning('回复内容至少 3 个字')
    return
  }
  if (!replyTarget.value) return
  replySubmitting.value = true
  try {
    await commentCourse(courseId.value, { content, parent_id: replyTarget.value.id })
    ElMessage.success('回复已提交，审核通过后公开显示')
    cancelReply()
  } catch (error) {
    /* 错误已提示 */
  } finally {
    replySubmitting.value = false
  }
}

/** 点赞 / 取消点赞评论 */
async function handleToggleLike(comment) {
  const id = comment.id
  commentBusy.value = { ...commentBusy.value, [id]: true }
  try {
    const data = comment.liked
      ? await unlikeCourseComment(id)
      : await likeCourseComment(id)
    comment.liked = Boolean(data?.liked ?? !comment.liked)
    comment.like_count = Number(data?.like_count ?? Math.max(0, Number(comment.like_count || 0) + (comment.liked ? 1 : -1)))
  } catch (error) {
    /* 错误已提示 */
  } finally {
    commentBusy.value = { ...commentBusy.value, [id]: false }
  }
}

/** 删除自己的评论 */
async function handleDeleteComment(comment) {
  try {
    await ElMessageBox.confirm('确定删除这条评论吗？', '删除评论', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消'
    })
  } catch (error) {
    return
  }
  try {
    await deleteCourseComment(comment.id)
    ElMessage.success('评论已删除')
    loadComments()
  } catch (error) {
    /* 错误已提示 */
  }
}

/** 是否是当前用户的评论 */
function isMine(item) {
  return Number(item?.user_id) === myUserId.value && myUserId.value > 0
}

/** 评论时间格式化（YYYY-MM-DD HH:mm） */
function formatTime(value) {
  if (!value) return ''
  const text = String(value).replace('T', ' ')
  return text.slice(0, 16)
}

/** 头像地址 */
function userAvatar(item) {
  return resolveAsset(item?.user_avatar || '')
}

/** 用户名首字（无头像时占位） */
function avatarInitial(item) {
  return (item?.user_name || 'U').slice(0, 1).toUpperCase()
}

// ---------------- 相关推荐 ----------------
const related = ref([])
const relatedLoading = ref(true)

/** 加载相关课程 */
async function loadRelated() {
  relatedLoading.value = true
  try {
    const data = await getRelatedCourses(courseId.value)
    related.value = Array.isArray(data) ? data : data?.items || []
  } catch (error) {
    related.value = []
  } finally {
    relatedLoading.value = false
  }
}

// ---------------- 初始化 ----------------
onMounted(async () => {
  await loadCourse()
  await Promise.all([loadRating(), loadComments(), loadRelated()])
})
</script>

<template>
  <div class="ft-page">
    <PageHeader
      :title="course?.title || '课程详情'"
      :subtitle="course?.subtitle || '跟练课程视频，完成后别忘了点赞与评分'"
      back-to="/courses"
    >
      <template #tag>
        <span v-if="course" class="ft-chip" :class="`ft-chip--${course.is_published === false ? '' : 'success'}`">
          {{ course.is_published === false ? '已下架' : '已上架' }}
        </span>
      </template>
      <template #actions>
        <el-button :loading="favoriteLoading" @click="handleToggleFavorite">
          {{ course?.is_favorited ? '★ 已收藏' : '☆ 收藏' }}
        </el-button>
        <el-button type="primary" :loading="videoLoading" @click="handlePlay">开始训练</el-button>
      </template>
    </PageHeader>

    <div v-if="loading" class="ft-loading-text">正在加载课程…</div>

    <EmptyState v-else-if="errorMsg" icon="⚠️" :description="errorMsg" error>
      <el-button @click="loadCourse">重新加载</el-button>
      <el-button @click="router.push('/courses')">返回课程中心</el-button>
    </EmptyState>

    <template v-else-if="course">
      <div class="course-detail">
        <!-- ============ 左侧：播放器 + 课程信息 ============ -->
        <div class="course-detail__main">
          <!-- 播放器 -->
          <section class="player">
            <!-- 已获取到可直接播放的地址 -->
            <video
              v-if="playerActive && isDirectPlayable"
              class="player__video"
              :src="videoUrl"
              controls
              autoplay
              playsinline
            ></video>

            <!-- 占位 / 无法直接播放 -->
            <div
              v-else
              class="player__placeholder"
              :style="coverUrl ? { backgroundImage: `url(${coverUrl})` } : {}"
            >
              <div class="player__overlay">
                <button class="player__play" type="button" :disabled="videoLoading" @click="handlePlay">
                  <svg viewBox="0 0 24 24" width="26" height="26" fill="currentColor">
                    <path d="M8 5v14l11-7z" />
                  </svg>
                </button>
                <p class="player__tip">
                  <template v-if="videoLoading">正在获取播放地址…</template>
                  <template v-else-if="videoError">{{ videoError }}</template>
                  <template v-else-if="playerActive && videoUrl">
                    该视频地址（{{ videoUrl.slice(-12) }}）不是 mp4/webm，暂不支持在线播放
                  </template>
                  <template v-else>点击播放（演示环境仅提供播放地址占位）</template>
                </p>
                <p v-if="videoUrl" class="player__url">{{ videoUrl }}</p>
                <p v-if="videoInfo?.expires_at" class="player__expire">
                  链接有效期至 {{ formatTime(videoInfo.expires_at) }}
                </p>
              </div>
            </div>
          </section>

          <!-- 课程信息 -->
          <section class="ft-card course-info">
            <div class="course-info__head">
              <div>
                <h2 class="course-info__title">{{ course.title }}</h2>
                <p class="course-info__meta">
                  <span v-if="course.category_name" class="ft-chip ft-chip--primary">{{ course.category_name }}</span>
                  <span class="ft-chip">{{ difficultyMap[course.difficulty] || '初级' }}</span>
                  <span class="ft-chip">{{ course.duration_min }} 分钟</span>
                  <span class="ft-chip">🔥 {{ course.calories }} 千卡</span>
                  <span v-if="course.coach_name" class="ft-chip">教练 {{ course.coach_name }}</span>
                </p>
              </div>
              <div class="course-info__rating">
                <p class="course-info__score">{{ Number(course.rating_avg || 0).toFixed(1) }}</p>
                <el-rate :model-value="Number(course.rating_avg || 0)" disabled allow-half />
                <p class="ft-muted" style="font-size: 11px">{{ course.rating_count || 0 }} 人评分</p>
              </div>
            </div>

            <p class="course-info__desc">{{ course.description || '暂无课程介绍' }}</p>

            <div class="course-info__stats">
              <div><span>播放量</span><strong>{{ course.view_count || 0 }}</strong></div>
              <div><span>收藏数</span><strong>{{ course.favorite_count || 0 }}</strong></div>
              <div><span>评论数</span><strong>{{ course.comment_count || 0 }}</strong></div>
              <div><span>所需器械</span><strong>{{ course.equipment || '自重' }}</strong></div>
              <div><span>锻炼部位</span><strong>{{ course.body_parts || '全身' }}</strong></div>
            </div>

            <!-- 打分 -->
            <div class="rate-box">
              <div class="rate-box__left">
                <p class="rate-box__label">给这个课程打分</p>
                <el-rate
                  v-model="myScore"
                  :disabled="ratingSaving"
                  show-score
                  score-template="{value} 星"
                  @change="handleRate"
                />
                <p class="ft-muted" style="font-size: 11px; margin-top: 4px">
                  <template v-if="rating.my_score">我的评分：{{ rating.my_score }} 星</template>
                  <template v-else>还没有评分，点击星星即可打分</template>
                </p>
              </div>
              <div class="rate-box__right">
                <el-button :loading="ratingLoading" size="small" @click="loadRating">刷新评分</el-button>
              </div>
            </div>
          </section>

          <!-- ============ 评论区 ============ -->
          <section class="ft-card">
            <div class="comment-head">
              <h3 class="ft-section-title" style="margin: 0">课程评论</h3>
              <span class="ft-muted" style="font-size: 12px">共 {{ commentTotal }} 条</span>
            </div>

            <!-- 发表评论 -->
            <div class="comment-editor">
              <el-input
                v-model="commentForm.content"
                type="textarea"
                :rows="3"
                maxlength="500"
                show-word-limit
                placeholder="说说你的训练感受（3-500 字，提交后需审核）"
              />
              <div class="comment-editor__foot">
                <span class="ft-muted" style="font-size: 11px">仅展示审核通过的评论</span>
                <el-button type="primary" :loading="commentSubmitting" @click="handleSubmitComment">
                  发表评论
                </el-button>
              </div>
            </div>

            <div v-if="commentsLoading" class="ft-loading-text" style="padding: 30px 0">评论加载中…</div>

            <EmptyState v-else-if="commentsError" size="sm" icon="⚠️" :description="commentsError" error>
              <el-button size="small" @click="loadComments">重试</el-button>
            </EmptyState>

            <EmptyState
              v-else-if="!comments.length"
              size="sm"
              icon="💬"
              description="还没有评论，来做第一个分享感受的人"
            />

            <ul v-else class="comment-list">
              <li v-for="item in comments" :key="item.id" class="comment">
                <el-avatar :size="36" :src="userAvatar(item)" class="comment__avatar">
                  {{ avatarInitial(item) }}
                </el-avatar>

                <div class="comment__body">
                  <div class="comment__head">
                    <span class="comment__name">{{ item.user_name || '匿名用户' }}</span>
                    <span class="comment__time">{{ formatTime(item.created_at) }}</span>
                  </div>
                  <p class="comment__content">{{ item.content }}</p>

                  <div class="comment__actions">
                    <el-button
                      link
                      size="small"
                      :loading="commentBusy[item.id]"
                      @click="handleToggleLike(item)"
                    >
                      {{ item.liked ? '❤️' : '🤍' }} {{ item.like_count || 0 }}
                    </el-button>
                    <el-button link size="small" @click="openReply(item)">回复</el-button>
                    <el-button v-if="isMine(item)" link size="small" type="danger" @click="handleDeleteComment(item)">
                      删除
                    </el-button>
                  </div>

                  <!-- 回复列表 -->
                  <ul v-if="item.replies?.length" class="reply-list">
                    <li v-for="reply in item.replies" :key="reply.id">
                      <span class="reply-list__name">{{ reply.user_name || '匿名用户' }}：</span>
                      <span class="reply-list__content">{{ reply.content }}</span>
                      <div class="reply-list__actions">
                        <el-button link size="small" @click="handleToggleLike(reply)">
                          {{ reply.liked ? '❤️' : '🤍' }} {{ reply.like_count || 0 }}
                        </el-button>
                        <span class="reply-list__time">{{ formatTime(reply.created_at) }}</span>
                      </div>
                    </li>
                  </ul>

                  <p v-if="item.reply_count > (item.replies?.length || 0)" class="reply-more">
                    还有 {{ item.reply_count - (item.replies?.length || 0) }} 条回复
                  </p>

                  <!-- 回复输入框 -->
                  <div v-if="replyTarget?.id === item.id" class="reply-editor">
                    <el-input
                      v-model="replyContent"
                      type="textarea"
                      :rows="2"
                      maxlength="500"
                      show-word-limit
                      :placeholder="`回复 ${item.user_name || '匿名用户'}`"
                    />
                    <div class="reply-editor__foot">
                      <el-button size="small" @click="cancelReply">取消</el-button>
                      <el-button size="small" type="primary" :loading="replySubmitting" @click="handleSubmitReply">
                        提交回复
                      </el-button>
                    </div>
                  </div>
                </div>
              </li>
            </ul>

            <div v-if="commentTotal > commentPageSize" class="ft-pager">
              <el-pagination
                layout="prev, pager, next, total"
                :current-page="commentPage"
                :page-size="commentPageSize"
                :total="commentTotal"
                background
                @current-change="handleCommentPageChange"
              />
            </div>
          </section>
        </div>

        <!-- ============ 右侧：相关推荐 ============ -->
        <aside class="course-detail__side">
          <section class="ft-card">
            <h3 class="ft-section-title">相关推荐</h3>

            <div v-if="relatedLoading" class="ft-loading-text" style="padding: 20px 0">加载中…</div>

            <EmptyState v-else-if="!related.length" size="sm" icon="🎬" description="暂无同类课程推荐" />

            <ul v-else class="related-list">
              <li
                v-for="item in related"
                :key="item.id"
                class="related-item"
                @click="router.push(`/courses/${item.id}`)"
              >
                <div
                  class="related-item__cover"
                  :style="item.cover ? { backgroundImage: `url(${resolveAsset(item.cover)})` } : {}"
                >
                  <span v-if="!item.cover">🎬</span>
                </div>
                <div class="related-item__info">
                  <p class="related-item__title">{{ item.title }}</p>
                  <p class="related-item__meta">
                    ⭐ {{ Number(item.rating_avg || 0).toFixed(1) }} · {{ item.duration_min }} 分钟 ·
                    {{ difficultyMap[item.difficulty] || '初级' }}
                  </p>
                </div>
              </li>
            </ul>
          </section>

          <section class="ft-card">
            <h3 class="ft-section-title">训练小贴士</h3>
            <ul class="tips-list">
              <li>训练前做 5-10 分钟动态热身，降低受伤风险。</li>
              <li>组间休息时长按课程标注执行，保证动作质量。</li>
              <li>训练后补充蛋白质与水分，帮助肌肉恢复。</li>
              <li>每周至少安排 1-2 天完全休息日。</li>
            </ul>
          </section>
        </aside>
      </div>
    </template>
  </div>
</template>

<style scoped>
.course-detail {
  display: grid;
  grid-template-columns: minmax(0, 1.7fr) minmax(260px, 1fr);
  gap: 16px;
  align-items: start;
}

.course-detail__main {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-width: 0;
}

.course-detail__side {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* ---------------- 播放器 ---------------- */
.player {
  position: relative;
  border-radius: var(--ft-radius);
  overflow: hidden;
  border: 1px solid var(--ft-border);
  background: #000;
  aspect-ratio: 16 / 9;
}

.player__video {
  width: 100%;
  height: 100%;
  object-fit: contain;
  background: #000;
}

.player__placeholder {
  width: 100%;
  height: 100%;
  background: linear-gradient(135deg, rgba(255, 90, 31, 0.24), rgba(40, 70, 160, 0.24));
  background-size: cover;
  background-position: center;
  display: flex;
  align-items: center;
  justify-content: center;
}

.player__overlay {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 16px;
  background: linear-gradient(180deg, rgba(10, 12, 16, 0.45), rgba(10, 12, 16, 0.72));
  text-align: center;
}

.player__play {
  width: 58px;
  height: 58px;
  border-radius: 50%;
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  background: linear-gradient(135deg, var(--ft-primary), #ff9248);
  box-shadow: 0 10px 30px rgba(255, 90, 31, 0.45);
  cursor: pointer;
  transition: transform 0.18s ease;
}

.player__play:hover {
  transform: scale(1.08);
}

.player__play:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.player__tip {
  font-size: 13px;
  color: #e9edf5;
}

.player__url {
  font-size: 11px;
  color: var(--ft-text-dim);
  word-break: break-all;
  max-width: 90%;
}

.player__expire {
  font-size: 11px;
  color: var(--ft-text-dim);
}

/* ---------------- 课程信息 ---------------- */
.course-info__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.course-info__title {
  font-size: 20px;
  line-height: 1.35;
}

.course-info__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

.course-info__rating {
  text-align: center;
  flex: 0 0 auto;
}

.course-info__score {
  font-size: 26px;
  font-weight: 700;
  color: var(--ft-warning);
  line-height: 1.1;
}

.course-info__desc {
  margin-top: 14px;
  font-size: 13px;
  line-height: 1.85;
  color: var(--ft-text-sub);
}

.course-info__stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(110px, 1fr));
  gap: 10px;
  margin-top: 16px;
}

.course-info__stats > div {
  padding: 10px 12px;
  border-radius: 11px;
  border: 1px solid var(--ft-border);
  background: rgba(255, 255, 255, 0.02);
}

.course-info__stats span {
  display: block;
  font-size: 11px;
  color: var(--ft-text-dim);
}

.course-info__stats strong {
  font-size: 14px;
}

/* 打分 */
.rate-box {
  margin-top: 16px;
  padding: 12px 14px;
  border-radius: var(--ft-radius);
  border: 1px dashed rgba(255, 90, 31, 0.4);
  background: var(--ft-primary-soft);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.rate-box__label {
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 4px;
}

/* ---------------- 评论 ---------------- */
.comment-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.comment-editor {
  margin: 14px 0;
}

.comment-editor__foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 8px;
}

.comment-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
  margin-top: 6px;
}

.comment {
  display: flex;
  gap: 10px;
  padding-bottom: 14px;
  border-bottom: 1px solid var(--ft-border);
}

.comment:last-child {
  border-bottom: none;
  padding-bottom: 0;
}

.comment__avatar {
  flex: 0 0 36px;
  background: linear-gradient(135deg, var(--ft-primary), #ff9248);
  color: #fff;
  font-size: 13px;
}

.comment__body {
  flex: 1;
  min-width: 0;
}

.comment__head {
  display: flex;
  align-items: center;
  gap: 10px;
}

.comment__name {
  font-size: 13px;
  font-weight: 600;
  color: var(--ft-text);
}

.comment__time {
  font-size: 11px;
  color: var(--ft-text-dim);
}

.comment__content {
  margin-top: 4px;
  font-size: 13px;
  line-height: 1.7;
  color: var(--ft-text-sub);
  word-break: break-word;
}

.comment__actions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
}

.reply-list {
  margin-top: 10px;
  padding: 10px 12px;
  border-radius: 11px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--ft-border);
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.reply-list li {
  font-size: 12px;
  line-height: 1.6;
}

.reply-list__name {
  color: var(--ft-primary-light);
}

.reply-list__content {
  color: var(--ft-text-sub);
}

.reply-list__actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.reply-list__time {
  font-size: 10px;
  color: var(--ft-text-dim);
}

.reply-more {
  margin-top: 6px;
  font-size: 11px;
  color: var(--ft-text-dim);
}

.reply-editor {
  margin-top: 10px;
}

.reply-editor__foot {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 8px;
}

/* ---------------- 相关推荐 ---------------- */
.related-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.related-item {
  display: flex;
  gap: 10px;
  padding: 8px;
  border-radius: 11px;
  border: 1px solid var(--ft-border);
  background: rgba(255, 255, 255, 0.02);
  cursor: pointer;
  transition: all 0.16s ease;
}

.related-item:hover {
  border-color: rgba(255, 90, 31, 0.45);
  background: var(--ft-primary-soft);
}

.related-item__cover {
  width: 76px;
  height: 52px;
  flex: 0 0 76px;
  border-radius: 9px;
  background: linear-gradient(135deg, rgba(255, 90, 31, 0.3), rgba(40, 70, 160, 0.24));
  background-size: cover;
  background-position: center;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
}

.related-item__info {
  min-width: 0;
}

.related-item__title {
  font-size: 12px;
  font-weight: 600;
  color: var(--ft-text);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.related-item__meta {
  margin-top: 4px;
  font-size: 11px;
  color: var(--ft-text-dim);
}

.tips-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: 12px;
  line-height: 1.7;
  color: var(--ft-text-sub);
}

.tips-list li {
  padding-left: 14px;
  position: relative;
}

.tips-list li::before {
  content: '·';
  position: absolute;
  left: 2px;
  color: var(--ft-primary);
  font-weight: 700;
}

@media (max-width: 1040px) {
  .course-detail {
    grid-template-columns: 1fr;
  }
}
</style>
