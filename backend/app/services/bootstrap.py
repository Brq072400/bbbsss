"""初始化数据：默认管理员 + 动作库/课程/食物/计划模板的种子数据。

首次启动（或表为空）时自动写入，保证系统开箱即用；
生产环境也可以用 sql/seed_data.sql 直接导入。
"""
from __future__ import annotations

import json
import logging

from sqlalchemy import func, select

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.course import Course, CourseCategory
from app.models.diet import Food
from app.models.exercise import Exercise, ExerciseCategory
from app.models.plan import PlanTemplate
from app.models.user import Admin

logger = logging.getLogger("fittrack.bootstrap")

# ------------------------------------------------------------------ 动作分类
EXERCISE_CATEGORIES: list[dict] = [
    {"name": "胸部", "slug": "chest", "body_part": "胸", "sort_order": 1},
    {"name": "背部", "slug": "back", "body_part": "背", "sort_order": 2},
    {"name": "腿部", "slug": "legs", "body_part": "腿", "sort_order": 3},
    {"name": "肩部", "slug": "shoulders", "body_part": "肩", "sort_order": 4},
    {"name": "手臂", "slug": "arms", "body_part": "手臂", "sort_order": 5},
    {"name": "核心", "slug": "core", "body_part": "核心", "sort_order": 6},
    {"name": "有氧", "slug": "cardio", "body_part": "全身", "sort_order": 7},
]

# ------------------------------------------------------------------ 动作库
EXERCISES: list[dict] = [
    # ---- 胸 ----
    dict(cat="chest", name="杠铃卧推", name_en="Barbell Bench Press", equipment="杠铃", difficulty=2,
         primary_muscles="胸大肌", secondary_muscles="三角肌前束,肱三头肌",
         description="仰卧于平板凳，双脚踩实地面，肩胛骨收紧下沉，将杠铃从架上取下，控制下放至胸部中下沿后推起。",
         key_points="1. 肩胛后缩下沉，保持胸部挺起；\n2. 手腕与前臂保持垂直，不要翻腕；\n3. 下放 2 秒，推起 1 秒，全程匀速。",
         common_mistakes="1. 屁股离凳借力；\n2. 杠铃砸胸弹起；\n3. 手肘完全外展成 90°，肩关节压力过大。",
         tips="下放时吸气，推起时呼气。",
         keywords="卧推,胸,杠铃,平板"),
    dict(cat="chest", name="哑铃飞鸟", name_en="Dumbbell Fly", equipment="哑铃", difficulty=2,
         primary_muscles="胸大肌", secondary_muscles="三角肌前束",
         description="仰卧平板凳，双手持哑铃于胸前，手肘微屈固定角度，向两侧打开至胸部有牵拉感后合拢。",
         key_points="1. 手肘始终保持 15-20 度微屈；\n2. 打开幅度以肩不痛为限；\n3. 合拢时想象抱住一棵大树。",
         common_mistakes="1. 用直臂做大重量，伤肩；\n2. 下放过深；\n3. 变成推举动作。",
         tips="打开吸气，合拢呼气。", keywords="飞鸟,胸,哑铃,夹胸"),
    dict(cat="chest", name="俯卧撑", name_en="Push-Up", equipment="自重", difficulty=1,
         primary_muscles="胸大肌", secondary_muscles="肱三头肌,核心",
         description="双手略宽于肩撑地，身体成一直线，屈肘下放至胸部离地约一拳，再推起。",
         key_points="1. 收紧核心与臀部，身体一条直线；\n2. 手肘与身体约 45 度；\n3. 全程颈部中立，眼睛看地面。",
         common_mistakes="1. 塌腰翘臀；\n2. 只做半程；\n3. 头部前探。",
         tips="下放吸气，推起呼气，可先从跪姿开始。", keywords="俯卧撑,胸,自重,推"),
    dict(cat="chest", name="上斜哑铃卧推", name_en="Incline Dumbbell Press", equipment="哑铃", difficulty=2,
         primary_muscles="胸大肌上束", secondary_muscles="三角肌前束,肱三头肌",
         description="上斜凳 30-45 度，双手持哑铃于胸上方，垂直向上推起再控制下放。",
         key_points="1. 凳子角度不超过 45 度，否则变成肩推；\n2. 推起时哑铃略微靠拢；\n3. 下放至胸部两侧。",
         common_mistakes="1. 角度过高；\n2. 腰部过度反弓；\n3. 哑铃相撞。",
         tips="呼吸节奏同卧推。", keywords="上斜,卧推,胸,哑铃"),
    # ---- 背 ----
    dict(cat="back", name="引体向上", name_en="Pull-Up", equipment="自重", difficulty=3,
         primary_muscles="背阔肌", secondary_muscles="肱二头肌,斜方肌中下束",
         description="正握单杠略宽于肩，收肩胛发力将身体拉起至下巴过杠，缓慢下放至手臂接近伸直。",
         key_points="1. 先沉肩再拉；\n2. 想象用手肘向下砸；\n3. 下放 2-3 秒，充分伸展背阔肌。",
         common_mistakes="1. 靠摆动借力；\n2. 只做上半程；\n3. 耸肩。",
         tips="上拉呼气，下放吸气。做不到可先用弹力带辅助。", keywords="引体,背,单杠,自重"),
    dict(cat="back", name="杠铃划船", name_en="Barbell Row", equipment="杠铃", difficulty=3,
         primary_muscles="背阔肌", secondary_muscles="菱形肌,斜方肌,肱二头肌",
         description="俯身约 45 度，背部挺直，将杠铃沿大腿拉向腹部，再控制下放。",
         key_points="1. 全程腰背挺直，核心收紧；\n2. 手肘贴身向后拉；\n3. 顶峰收缩 1 秒。",
         common_mistakes="1. 弓背；\n2. 用腰甩重量；\n3. 拉得太高到胸口。",
         tips="拉起呼气，下放吸气。", keywords="划船,背,杠铃,俯身"),
    dict(cat="back", name="高位下拉", name_en="Lat Pulldown", equipment="器械", difficulty=1,
         primary_muscles="背阔肌", secondary_muscles="肱二头肌",
         description="坐姿固定大腿，宽握横杆下拉至锁骨上方，控制回放。",
         key_points="1. 身体略微后仰 10-15 度；\n2. 想象用手肘把杆拉下来；\n3. 回放充分伸展背阔。",
         common_mistakes="1. 拉至颈后；\n2. 用力过猛身体前后晃；\n3. 耸肩。",
         tips="下拉呼气，回放吸气。", keywords="下拉,背,器械,高位"),
    dict(cat="back", name="坐姿划船", name_en="Seated Cable Row", equipment="器械", difficulty=1,
         primary_muscles="菱形肌,背阔肌", secondary_muscles="肱二头肌",
         description="坐姿双脚踩踏板，挺胸将把手拉向腹部，肩胛后缩，控制回放。",
         key_points="1. 胸口挺起，不驼背；\n2. 拉到腹部后再夹紧肩胛 1 秒；\n3. 回放时肩胛前伸但不弓腰。",
         common_mistakes="1. 用腰后仰借力；\n2. 只用手臂拉；\n3. 重量过大。",
         tips="拉时呼气，回放吸气。", keywords="划船,坐姿,背,器械"),
    # ---- 腿 ----
    dict(cat="legs", name="杠铃深蹲", name_en="Barbell Squat", equipment="杠铃", difficulty=3,
         primary_muscles="股四头肌,臀大肌", secondary_muscles="腘绳肌,核心",
         description="杠铃置于斜方肌上方，双脚与肩同宽，屈髋屈膝下蹲至大腿平行地面后站起。",
         key_points="1. 膝盖与脚尖方向一致；\n2. 全程核心收紧、背部中立；\n3. 重心在全脚掌，脚跟不抬。",
         common_mistakes="1. 膝盖内扣；\n2. 弓腰；\n3. 半蹲就起。",
         tips="下蹲吸气，站起呼气。", keywords="深蹲,腿,杠铃,下肢"),
    dict(cat="legs", name="罗马尼亚硬拉", name_en="Romanian Deadlift", equipment="杠铃", difficulty=3,
         primary_muscles="腘绳肌,臀大肌", secondary_muscles="竖脊肌",
         description="双手持杠站立，膝盖微屈固定，屈髋向后推髋下放杠铃至小腿中段，感受大腿后侧牵拉后起身。",
         key_points="1. 全程背部挺直，杠铃贴近腿；\n2. 以屈髋为主，不要变深蹲；\n3. 起身时收臀发力。",
         common_mistakes="1. 弓背；\n2. 膝盖过度弯曲；\n3. 下放过低导致腰部代偿。",
         tips="下放吸气，起身呼气。", keywords="硬拉,臀,腿,腿后侧"),
    dict(cat="legs", name="弓箭步", name_en="Lunge", equipment="自重", difficulty=2,
         primary_muscles="股四头肌,臀大肌", secondary_muscles="腘绳肌,核心",
         description="一脚向前跨出，屈膝下蹲至后膝接近地面，再蹬地回到起始位，左右交替。",
         key_points="1. 前膝不超过脚尖太多；\n2. 躯干保持直立；\n3. 后腿膝盖朝地面而非前冲。",
         common_mistakes="1. 步幅过小；\n2. 身体前倾；\n3. 前膝内扣。",
         tips="下蹲吸气，站起呼气。", keywords="箭步蹲,弓步,腿,臀"),
    dict(cat="legs", name="臀桥", name_en="Glute Bridge", equipment="自重", difficulty=1,
         primary_muscles="臀大肌", secondary_muscles="腘绳肌,核心",
         description="仰卧屈膝脚踩地，收紧臀部将髋部顶起至身体成一直线，顶点停留后放下。",
         key_points="1. 用臀部发力，不要用腰；\n2. 顶点收紧臀部 2 秒；\n3. 下巴微收。",
         common_mistakes="1. 腰部过度反弓；\n2. 脚离臀太远；\n3. 速度过快。",
         tips="顶起呼气，放下吸气。", keywords="臀桥,臀,髋,自重"),
    # ---- 肩 ----
    dict(cat="shoulders", name="哑铃肩上推举", name_en="Dumbbell Shoulder Press", equipment="哑铃", difficulty=2,
         primary_muscles="三角肌前中束", secondary_muscles="肱三头肌",
         description="坐姿或站姿，双手持哑铃于耳侧，向上推起至手臂接近伸直，控制下放。",
         key_points="1. 核心收紧，不塌腰；\n2. 推起时手肘略微向内收；\n3. 下放至耳侧高度即可。",
         common_mistakes="1. 腰部反弓借力；\n2. 手肘完全外展；\n3. 下放过低。",
         tips="推起呼气，下放吸气。", keywords="推举,肩,哑铃,三角肌"),
    dict(cat="shoulders", name="哑铃侧平举", name_en="Lateral Raise", equipment="哑铃", difficulty=1,
         primary_muscles="三角肌中束", secondary_muscles="斜方肌",
         description="站立双手持哑铃于体侧，手肘微屈，向两侧举起至与肩同高，控制下放。",
         key_points="1. 小重量多次数；\n2. 手肘略微弯曲并领先于手腕；\n3. 举到肩高即可，不要过肩。",
         common_mistakes="1. 耸肩；\n2. 用惯性甩；\n3. 重量过大导致代偿。",
         tips="举起呼气，下放吸气。", keywords="侧平举,肩,哑铃,中束"),
    dict(cat="shoulders", name="面拉", name_en="Face Pull", equipment="器械", difficulty=1,
         primary_muscles="三角肌后束", secondary_muscles="菱形肌,斜方肌中束",
         description="绳索调至高位，双手抓绳向面部方向拉，手肘高于手腕，末端外旋肩关节。",
         key_points="1. 拉向眉毛位置；\n2. 末端外旋，肩胛后缩；\n3. 轻重量高次数。",
         common_mistakes="1. 重量过大变划船；\n2. 耸肩；\n3. 身体后仰。",
         tips="拉时呼气，回放吸气。", keywords="面拉,肩,后束,绳索"),
    # ---- 手臂 ----
    dict(cat="arms", name="哑铃弯举", name_en="Dumbbell Curl", equipment="哑铃", difficulty=1,
         primary_muscles="肱二头肌", secondary_muscles="肱肌",
         description="站立双手持哑铃，大臂贴身固定，屈肘将哑铃举至肩前后控制下放。",
         key_points="1. 大臂不前后摆动；\n2. 顶峰收缩 1 秒；\n3. 下放 2-3 秒。",
         common_mistakes="1. 甩腰借力；\n2. 手腕翻折；\n3. 下放太快。",
         tips="举起呼气，下放吸气。", keywords="弯举,二头,手臂,哑铃"),
    dict(cat="arms", name="窄距俯卧撑", name_en="Close-Grip Push-Up", equipment="自重", difficulty=2,
         primary_muscles="肱三头肌", secondary_muscles="胸大肌,核心",
         description="双手与肩同宽或略窄撑地，身体成直线，屈肘下放再推起，手肘贴近身体。",
         key_points="1. 手肘贴身不外展；\n2. 核心收紧；\n3. 全程控制。",
         common_mistakes="1. 塌腰；\n2. 手肘外翻；\n3. 幅度不足。",
         tips="下放吸气，推起呼气。", keywords="窄距,三头,手臂,俯卧撑"),
    dict(cat="arms", name="绳索下压", name_en="Triceps Pushdown", equipment="器械", difficulty=1,
         primary_muscles="肱三头肌", secondary_muscles="",
         description="面对绳索机站立，大臂贴身，握住绳索向下压至手臂伸直，控制回放。",
         key_points="1. 大臂固定不晃；\n2. 伸直时收缩三头 1 秒；\n3. 回放至手肘约 90 度。",
         common_mistakes="1. 耸肩；\n2. 身体前倾借力；\n3. 大臂前后摆动。",
         tips="下压呼气，回放吸气。", keywords="下压,三头,手臂,绳索"),
    # ---- 核心 ----
    dict(cat="core", name="平板支撑", name_en="Plank", equipment="自重", difficulty=1,
         primary_muscles="腹横肌", secondary_muscles="竖脊肌,肩部",
         description="肘部与前臂着地，身体从头到脚成一条直线，收紧核心保持静止。",
         key_points="1. 臀部不塌不翘；\n2. 收紧腹部与臀部；\n3. 保持正常呼吸。",
         common_mistakes="1. 塌腰；\n2. 憋气；\n3. 抬臀。",
         tips="均匀呼吸，力竭前 5 秒收尾。", keywords="平板支撑,核心,腹,静力"),
    dict(cat="core", name="卷腹", name_en="Crunch", equipment="自重", difficulty=1,
         primary_muscles="腹直肌", secondary_muscles="",
         description="仰卧屈膝，双手轻放耳侧，用腹部力量将肩胛骨抬离地面后缓慢放下。",
         key_points="1. 下颌与胸保持一拳距离；\n2. 用腹肌发力而非脖子；\n3. 下放不放松到底。",
         common_mistakes="1. 用手拉脖子；\n2. 幅度过大变成仰卧起坐；\n3. 借力弹起。",
         tips="起身呼气，下放吸气。", keywords="卷腹,腹肌,核心,自重"),
    dict(cat="core", name="仰卧举腿", name_en="Lying Leg Raise", equipment="自重", difficulty=2,
         primary_muscles="腹直肌下部", secondary_muscles="髂腰肌",
         description="仰卧双手放体侧，双腿并拢伸直抬起至与地面垂直后缓慢下放。",
         key_points="1. 下背部贴地；\n2. 下放速度慢，避免腰部拱起；\n3. 腿不触地保持张力。",
         common_mistakes="1. 腰部离地；\n2. 用惯性甩腿；\n3. 颈部紧张。",
         tips="抬腿呼气，下放吸气。", keywords="举腿,下腹,核心"),
    dict(cat="core", name="俄罗斯转体", name_en="Russian Twist", equipment="自重", difficulty=2,
         primary_muscles="腹斜肌", secondary_muscles="腹直肌",
         description="坐姿上身后仰约 45 度，双脚可离地，双手持重物左右转体触地。",
         key_points="1. 转体来自躯干而非手臂；\n2. 保持背部挺直；\n3. 控制节奏。",
         common_mistakes="1. 含胸弓背；\n2. 只动手臂；\n3. 速度过快。",
         tips="转体呼气，回正吸气。", keywords="转体,腹斜肌,核心"),
    # ---- 有氧 ----
    dict(cat="cardio", name="开合跳", name_en="Jumping Jack", equipment="自重", difficulty=1,
         primary_muscles="全身", secondary_muscles="心肺",
         description="站立起跳，双腿分开同时双臂上举过头，再跳回并拢，连续进行。",
         key_points="1. 落地屈膝缓冲；\n2. 保持节奏与呼吸；\n3. 手臂过头。",
         common_mistakes="1. 落地僵硬；\n2. 幅度过小；\n3. 憋气。",
         tips="匀速呼吸，按时间或次数做。", keywords="开合跳,有氧,热身,HIIT"),
    dict(cat="cardio", name="高抬腿", name_en="High Knees", equipment="自重", difficulty=2,
         primary_muscles="髂腰肌,股四头肌", secondary_muscles="心肺,核心",
         description="原地跑动，膝盖尽量抬高至髋部高度，双臂配合摆动。",
         key_points="1. 前脚掌着地；\n2. 躯干直立不后仰；\n3. 频率优先于幅度。",
         common_mistakes="1. 后仰；\n2. 脚跟着地；\n3. 手臂不摆动。",
         tips="短时间高强度，注意呼吸节奏。", keywords="高抬腿,有氧,HIIT,心肺"),
    dict(cat="cardio", name="波比跳", name_en="Burpee", equipment="自重", difficulty=3,
         primary_muscles="全身", secondary_muscles="心肺",
         description="下蹲撑地→双腿后跳成俯撑→俯卧撑→收腿站起跳跃，一套连贯完成。",
         key_points="1. 全程核心收紧；\n2. 落地缓冲；\n3. 呼吸与动作节奏匹配。",
         common_mistakes="1. 塌腰；\n2. 中间停顿过久；\n3. 落地不缓冲。",
         tips="新手可去掉跳跃或俯卧撑环节。", keywords="波比,有氧,HIIT,全身"),
    dict(cat="cardio", name="跳绳", name_en="Jump Rope", equipment="跳绳", difficulty=2,
         primary_muscles="小腿,全身", secondary_muscles="心肺",
         description="双手持绳，前脚掌轻跳，手腕发力摇绳，保持稳定节奏。",
         key_points="1. 前脚掌落地；\n2. 手腕摇绳而非大臂；\n3. 跳跃高度只要过绳即可。",
         common_mistakes="1. 跳太高；\n2. 全脚掌砸地；\n3. 大臂大幅摆动。",
         tips="每组 1-2 分钟，组间休息 30-60 秒。", keywords="跳绳,有氧,心肺"),
    dict(cat="cardio", name="慢跑", name_en="Jogging", equipment="自重", difficulty=1,
         primary_muscles="下肢", secondary_muscles="心肺",
         description="以能边跑边说话的强度持续跑动，心率控制在最大心率的 60-70%。",
         key_points="1. 步频 170-180; \n2. 中足着地；\n3. 上身放松。",
         common_mistakes="1. 步幅过大；\n2. 手臂横摆；\n3. 一开始冲太快。",
         tips="热身 5 分钟，结束后拉伸。", keywords="跑步,慢跑,有氧"),
    dict(cat="cardio", name="山地登山者", name_en="Mountain Climber", equipment="自重", difficulty=2,
         primary_muscles="核心,髋屈肌", secondary_muscles="心肺,肩",
         description="俯撑姿势，双腿交替快速向胸部收膝，像原地爬山。",
         key_points="1. 臀部高度稳定；\n2. 核心收紧；\n3. 交替节奏均匀。",
         common_mistakes="1. 臀部上下起伏；\n2. 塌腰；\n3. 脚落地太重。",
         tips="30 秒一组，配合呼吸。", keywords="登山者,核心,有氧,HIIT"),
]

# ------------------------------------------------------------------ 课程分类
COURSE_CATEGORIES: list[dict] = [
    {"name": "力量训练", "slug": "strength", "sort_order": 1},
    {"name": "有氧燃脂", "slug": "cardio", "sort_order": 2},
    {"name": "拉伸放松", "slug": "stretch", "sort_order": 3},
    {"name": "HIIT 高强度", "slug": "hiit", "sort_order": 4},
    {"name": "瑜伽", "slug": "yoga", "sort_order": 5},
]

# ------------------------------------------------------------------ 课程
COURSES: list[dict] = [
    dict(cat="strength", title="哑铃全身力量入门", subtitle="新手第一课", duration_min=25, calories=180,
         difficulty=1, equipment="哑铃", body_parts="全身", coach_name="Coach Leo",
         description="用一对哑铃完成推、拉、蹲、髋铰链四个基本模式，建立全身力量基础。"),
    dict(cat="strength", title="胸肩背分化训练（上肢日）", subtitle="一周三练进阶", duration_min=40, calories=300,
         difficulty=2, equipment="哑铃,哑铃凳", body_parts="胸,肩,背", coach_name="Coach Leo",
         description="胸推、肩推、划船三大动作组合，兼顾力量与形态。"),
    dict(cat="strength", title="下肢力量强化", subtitle="深蹲硬拉组合", duration_min=35, calories=350,
         difficulty=3, equipment="杠铃", body_parts="腿,臀", coach_name="Coach Amy",
         description="以深蹲、罗马尼亚硬拉为核心的下肢力量课，适合有一定基础者。"),
    dict(cat="cardio", title="20 分钟居家燃脂有氧", subtitle="无需器械", duration_min=20, calories=220,
         difficulty=1, equipment="无", body_parts="全身", coach_name="Coach Mia",
         description="开合跳、高抬腿、登山者循环，心率稳定在燃脂区间。"),
    dict(cat="cardio", title="低冲击有氧塑形", subtitle="膝盖友好", duration_min=30, calories=260,
         difficulty=1, equipment="无", body_parts="全身,臀,腿", coach_name="Coach Mia",
         description="无跳跃动作，适合体重基数较大或膝盖需要保护的人群。"),
    dict(cat="stretch", title="睡前 10 分钟全身拉伸", subtitle="改善睡眠", duration_min=10, calories=40,
         difficulty=1, equipment="瑜伽垫", body_parts="全身", coach_name="Coach Amy",
         description="从颈部到小腿的静态拉伸序列，每个动作保持 30 秒，放松紧张肌群。"),
    dict(cat="stretch", title="久坐族肩颈放松", subtitle="办公室也能做", duration_min=12, calories=45,
         difficulty=1, equipment="无", body_parts="肩,颈,背", coach_name="Coach Amy",
         description="针对圆肩驼背与肩颈僵硬的拉伸与激活动作。"),
    dict(cat="hiit", title="TABATA 四分钟极限燃脂", subtitle="4 分钟 8 轮", duration_min=4, calories=70,
         difficulty=3, equipment="无", body_parts="全身", coach_name="Coach Leo",
         description="20 秒全力 10 秒休息，8 轮共 4 分钟，建议做 3-5 组。"),
    dict(cat="hiit", title="HIIT 燃脂 20 分钟", subtitle="中等强度循环", duration_min=20, calories=280,
         difficulty=2, equipment="无", body_parts="全身", coach_name="Coach Leo",
         description="6 个动作 × 4 轮，40 秒训练 20 秒休息。"),
    dict(cat="yoga", title="晨间唤醒流瑜伽", subtitle="15 分钟开启一天", duration_min=15, calories=90,
         difficulty=1, equipment="瑜伽垫", body_parts="全身", coach_name="Coach Luna",
         description="拜日式串联，配合呼吸唤醒身体与脊柱。"),
    dict(cat="yoga", title="髋部打开与放松", subtitle="改善骨盆灵活性", duration_min=20, calories=80,
         difficulty=2, equipment="瑜伽垫,瑜伽砖", body_parts="髋,腿", coach_name="Coach Luna",
         description="针对久坐导致的髋屈肌紧张，做深度髋部打开。"),
    dict(cat="yoga", title="核心稳定流", subtitle="腹背协同", duration_min=18, calories=110,
         difficulty=2, equipment="瑜伽垫", body_parts="核心", coach_name="Coach Luna",
         description="以平板、船式、侧板为主的稳定序列，提升核心抗屈伸能力。"),
]

# ------------------------------------------------------------------ 食物库（每 100g）
FOODS: list[dict] = [
    dict(name="米饭", category="主食", calories=116, protein=2.6, fat=0.3, carbohydrate=25.9, fiber=0.3),
    dict(name="全麦面包", category="主食", calories=246, protein=9.0, fat=3.3, carbohydrate=45.0, fiber=6.0),
    dict(name="燕麦片", category="主食", calories=377, protein=15.0, fat=6.6, carbohydrate=61.0, fiber=9.6),
    dict(name="红薯", category="主食", calories=90, protein=1.4, fat=0.2, carbohydrate=20.9, fiber=2.4),
    dict(name="玉米", category="主食", calories=112, protein=4.0, fat=1.2, carbohydrate=22.8, fiber=2.9),
    dict(name="意大利面", category="主食", calories=350, protein=12.0, fat=1.5, carbohydrate=72.0, fiber=3.0),
    dict(name="荞麦面", category="主食", calories=340, protein=13.0, fat=2.4, carbohydrate=68.0, fiber=5.0),
    dict(name="土豆", category="主食", calories=77, protein=2.0, fat=0.2, carbohydrate=17.2, fiber=2.2),
    dict(name="鸡胸肉", category="肉蛋", calories=133, protein=19.4, fat=5.0, carbohydrate=2.5, fiber=0),
    dict(name="鸡蛋", category="肉蛋", calories=144, protein=13.3, fat=8.8, carbohydrate=2.8, fiber=0),
    dict(name="牛肉(瘦)", category="肉蛋", calories=106, protein=20.2, fat=2.3, carbohydrate=1.2, fiber=0),
    dict(name="三文鱼", category="肉蛋", calories=139, protein=17.2, fat=7.8, carbohydrate=0, fiber=0),
    dict(name="虾仁", category="肉蛋", calories=93, protein=18.6, fat=0.8, carbohydrate=2.8, fiber=0),
    dict(name="龙利鱼", category="肉蛋", calories=87, protein=17.0, fat=1.5, carbohydrate=0, fiber=0),
    dict(name="牛奶", category="乳品", calories=54, protein=3.0, fat=3.2, carbohydrate=3.4, fiber=0),
    dict(name="无糖酸奶", category="乳品", calories=72, protein=3.5, fat=3.3, carbohydrate=5.0, fiber=0),
    dict(name="低脂奶酪", category="乳品", calories=260, protein=30.0, fat=15.0, carbohydrate=2.0, fiber=0),
    dict(name="西兰花", category="蔬菜", calories=36, protein=4.1, fat=0.6, carbohydrate=4.3, fiber=1.6),
    dict(name="菠菜", category="蔬菜", calories=28, protein=2.6, fat=0.3, carbohydrate=4.5, fiber=1.7),
    dict(name="生菜", category="蔬菜", calories=16, protein=1.4, fat=0.3, carbohydrate=2.1, fiber=0.7),
    dict(name="番茄", category="蔬菜", calories=20, protein=0.9, fat=0.2, carbohydrate=4.0, fiber=0.5),
    dict(name="黄瓜", category="蔬菜", calories=16, protein=0.8, fat=0.2, carbohydrate=2.9, fiber=0.5),
    dict(name="胡萝卜", category="蔬菜", calories=41, protein=0.9, fat=0.2, carbohydrate=9.6, fiber=2.8),
    dict(name="香菇", category="蔬菜", calories=26, protein=2.2, fat=0.3, carbohydrate=5.2, fiber=3.3),
    dict(name="苹果", category="水果", calories=52, protein=0.3, fat=0.2, carbohydrate=13.8, fiber=2.4),
    dict(name="香蕉", category="水果", calories=89, protein=1.1, fat=0.3, carbohydrate=22.8, fiber=2.6),
    dict(name="蓝莓", category="水果", calories=57, protein=0.7, fat=0.3, carbohydrate=14.5, fiber=2.4),
    dict(name="橙子", category="水果", calories=47, protein=0.9, fat=0.1, carbohydrate=11.8, fiber=2.4),
    dict(name="牛油果", category="水果", calories=160, protein=2.0, fat=15.0, carbohydrate=8.5, fiber=6.7),
    dict(name="杏仁", category="零食", calories=579, protein=21.2, fat=49.9, carbohydrate=21.6, fiber=12.5),
    dict(name="花生米", category="零食", calories=567, protein=25.8, fat=49.2, carbohydrate=16.1, fiber=8.5),
    dict(name="黑巧克力", category="零食", calories=546, protein=4.9, fat=31.3, carbohydrate=61.2, fiber=7.0),
    dict(name="蛋白粉", category="零食", calories=380, protein=80.0, fat=4.0, carbohydrate=6.0, fiber=0),
    dict(name="豆腐", category="肉蛋", calories=76, protein=8.1, fat=4.8, carbohydrate=1.9, fiber=0.4),
    dict(name="豆浆(无糖)", category="乳品", calories=31, protein=3.0, fat=1.6, carbohydrate=1.2, fiber=0.5),
]

# ------------------------------------------------------------------ 计划模板
PLAN_TEMPLATES: list[dict] = [
    dict(name="新手全身 3 日循环", category="新手", goal="keep_fit", difficulty=1, cycle_type="weekly", cycle_days=7,
         description="周一/三/五全身训练，其余日休息或轻度有氧，最适合刚开始健身的人。",
         items=[
             {"day_index": 1, "items": [
                 {"exercise": "杠铃深蹲", "sets": 3, "reps": 10, "rest_seconds": 90},
                 {"exercise": "俯卧撑", "sets": 3, "reps": 12, "rest_seconds": 60},
                 {"exercise": "高位下拉", "sets": 3, "reps": 12, "rest_seconds": 60},
                 {"exercise": "平板支撑", "sets": 3, "reps": 1, "duration_min": 1, "rest_seconds": 45},
             ]},
             {"day_index": 3, "items": [
                 {"exercise": "哑铃肩上推举", "sets": 3, "reps": 12, "rest_seconds": 60},
                 {"exercise": "坐姿划船", "sets": 3, "reps": 12, "rest_seconds": 60},
                 {"exercise": "臀桥", "sets": 3, "reps": 15, "rest_seconds": 45},
                 {"exercise": "卷腹", "sets": 3, "reps": 15, "rest_seconds": 45},
             ]},
             {"day_index": 5, "items": [
                 {"exercise": "罗马尼亚硬拉", "sets": 3, "reps": 10, "rest_seconds": 90},
                 {"exercise": "哑铃飞鸟", "sets": 3, "reps": 12, "rest_seconds": 60},
                 {"exercise": "面拉", "sets": 3, "reps": 15, "rest_seconds": 45},
                 {"exercise": "慢跑", "sets": 1, "reps": 1, "duration_min": 20},
             ]},
         ]),
    dict(name="减脂 HIIT + 有氧 计划", category="减脂", goal="lose_fat", difficulty=2, cycle_type="weekly", cycle_days=7,
         description="以 HIIT 与低强度有氧交替，配合核心训练，适合想快速减脂的人。",
         items=[
             {"day_index": 1, "items": [
                 {"exercise": "波比跳", "sets": 4, "reps": 10, "rest_seconds": 45},
                 {"exercise": "高抬腿", "sets": 4, "reps": 1, "duration_min": 1, "rest_seconds": 30},
                 {"exercise": "山地登山者", "sets": 4, "reps": 1, "duration_min": 1, "rest_seconds": 30},
             ]},
             {"day_index": 2, "items": [
                 {"exercise": "慢跑", "sets": 1, "reps": 1, "duration_min": 30},
                 {"exercise": "平板支撑", "sets": 3, "reps": 1, "duration_min": 1, "rest_seconds": 45},
             ]},
             {"day_index": 4, "items": [
                 {"exercise": "跳绳", "sets": 5, "reps": 1, "duration_min": 2, "rest_seconds": 45},
                 {"exercise": "仰卧举腿", "sets": 3, "reps": 15, "rest_seconds": 45},
             ]},
             {"day_index": 6, "items": [
                 {"exercise": "开合跳", "sets": 5, "reps": 1, "duration_min": 1, "rest_seconds": 30},
                 {"exercise": "俄罗斯转体", "sets": 3, "reps": 20, "rest_seconds": 45},
             ]},
         ]),
    dict(name="增肌上下肢 4 日分化", category="增肌", goal="gain_muscle", difficulty=3, cycle_type="weekly", cycle_days=7,
         description="上肢/下肢各两天，给大肌群足够刺激与恢复时间。",
         items=[
             {"day_index": 1, "items": [
                 {"exercise": "杠铃卧推", "sets": 4, "reps": 8, "rest_seconds": 120},
                 {"exercise": "杠铃划船", "sets": 4, "reps": 8, "rest_seconds": 120},
                 {"exercise": "哑铃侧平举", "sets": 3, "reps": 15, "rest_seconds": 60},
                 {"exercise": "绳索下压", "sets": 3, "reps": 12, "rest_seconds": 60},
             ]},
             {"day_index": 2, "items": [
                 {"exercise": "杠铃深蹲", "sets": 5, "reps": 6, "rest_seconds": 150},
                 {"exercise": "罗马尼亚硬拉", "sets": 4, "reps": 8, "rest_seconds": 120},
                 {"exercise": "弓箭步", "sets": 3, "reps": 12, "rest_seconds": 90},
                 {"exercise": "臀桥", "sets": 3, "reps": 15, "rest_seconds": 60},
             ]},
             {"day_index": 4, "items": [
                 {"exercise": "上斜哑铃卧推", "sets": 4, "reps": 10, "rest_seconds": 90},
                 {"exercise": "引体向上", "sets": 4, "reps": 6, "rest_seconds": 120},
                 {"exercise": "面拉", "sets": 3, "reps": 15, "rest_seconds": 60},
                 {"exercise": "哑铃弯举", "sets": 3, "reps": 12, "rest_seconds": 60},
             ]},
             {"day_index": 5, "items": [
                 {"exercise": "罗马尼亚硬拉", "sets": 4, "reps": 8, "rest_seconds": 120},
                 {"exercise": "哑铃肩上推举", "sets": 4, "reps": 10, "rest_seconds": 90},
                 {"exercise": "仰卧举腿", "sets": 3, "reps": 15, "rest_seconds": 45},
             ]},
         ]),
]


def ensure_default_admin() -> None:
    """首次启动创建默认管理员（用户名/密码见 settings）。"""
    with SessionLocal() as db:
        exists = db.scalar(select(func.count()).select_from(Admin)) or 0
        if exists:
            return
        db.add(Admin(
            username=settings.DEFAULT_ADMIN_USERNAME,
            password_hash=hash_password(settings.DEFAULT_ADMIN_PASSWORD),
            real_name="超级管理员",
            role="super",
        ))
        db.commit()
        logger.info("已创建默认管理员：%s / %s", settings.DEFAULT_ADMIN_USERNAME, settings.DEFAULT_ADMIN_PASSWORD)


def ensure_seed_data() -> None:
    """首次启动写入动作库/课程/食物/计划模板等演示数据。"""
    with SessionLocal() as db:
        # ---- 动作分类 + 动作 ----
        if not (db.scalar(select(func.count()).select_from(ExerciseCategory)) or 0):
            cat_map: dict[str, int] = {}
            for c in EXERCISE_CATEGORIES:
                obj = ExerciseCategory(**c)
                db.add(obj)
                db.flush()
                cat_map[c["slug"]] = obj.id
            for e in EXERCISES:
                data = dict(e)
                slug = data.pop("cat")
                db.add(Exercise(category_id=cat_map[slug], **data))
            db.commit()
            logger.info("已写入 %d 个动作分类、%d 个动作", len(EXERCISE_CATEGORIES), len(EXERCISES))

        # ---- 课程分类 + 课程 ----
        if not (db.scalar(select(func.count()).select_from(CourseCategory)) or 0):
            ccat: dict[str, int] = {}
            for c in COURSE_CATEGORIES:
                obj = CourseCategory(**c)
                db.add(obj)
                db.flush()
                ccat[c["slug"]] = obj.id
            for idx, c in enumerate(COURSES):
                data = dict(c)
                slug = data.pop("cat")
                db.add(Course(
                    category_id=ccat[slug],
                    cover=f"/static/covers/{slug}.jpg",
                    video_url=f"https://example.com/videos/{slug}-{idx + 1}.mp4",
                    sort_order=idx,
                    **{k: v for k, v in data.items() if k != "cat"},
                ))
            db.commit()
            logger.info("已写入 %d 个课程分类、%d 门课程", len(COURSE_CATEGORIES), len(COURSES))

        # ---- 食物库 ----
        if not (db.scalar(select(func.count()).select_from(Food)) or 0):
            for f in FOODS:
                db.add(Food(**f))
            db.commit()
            logger.info("已写入 %d 条食物数据", len(FOODS))

        # ---- 计划模板 ----
        if not (db.scalar(select(func.count()).select_from(PlanTemplate)) or 0):
            for t in PLAN_TEMPLATES:
                data = dict(t)
                items = data.pop("items")
                db.add(PlanTemplate(items_json=json.dumps(items, ensure_ascii=False), is_official=True, **data))
            db.commit()
            logger.info("已写入 %d 个计划模板", len(PLAN_TEMPLATES))
