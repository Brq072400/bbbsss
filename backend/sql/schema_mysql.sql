-- ============================================================
-- FitTrack 健身系统 —— MySQL 8.0 建表脚本
-- 由 backend/tools/gen_sql.py 从 SQLAlchemy 模型自动生成，请勿手改
-- 字符集统一 utf8mb4，引擎 InnoDB
-- ============================================================

CREATE DATABASE IF NOT EXISTS `fittrack` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE `fittrack`;

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- 后台管理员表
CREATE TABLE IF NOT EXISTS admins (
	id INTEGER AUTO_INCREMENT NOT NULL COMMENT '管理员ID', 
	username VARCHAR(50) NOT NULL COMMENT '登录名', 
	password_hash VARCHAR(255) NOT NULL COMMENT '密码哈希', 
	real_name VARCHAR(50) COMMENT '真实姓名', 
	`role` VARCHAR(20) NOT NULL COMMENT '角色 super/admin', 
	is_active BOOL NOT NULL COMMENT '是否启用', 
	last_login_at DATETIME COMMENT '最后登录时间', 
	created_at DATETIME NOT NULL COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP, 
	updated_at DATETIME NOT NULL COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id)
)COMMENT='后台管理员表' ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE UNIQUE INDEX ix_admins_username ON admins (username);

-- 课程分类表
CREATE TABLE IF NOT EXISTS course_categories (
	id INTEGER AUTO_INCREMENT NOT NULL, 
	name VARCHAR(50) NOT NULL COMMENT '分类名称', 
	slug VARCHAR(50) NOT NULL COMMENT '英文标识', 
	icon VARCHAR(255) COMMENT '分类图标', 
	sort_order INTEGER NOT NULL COMMENT '排序', 
	is_active BOOL NOT NULL COMMENT '是否启用', 
	created_at DATETIME NOT NULL COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP, 
	updated_at DATETIME NOT NULL COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	UNIQUE (name), 
	UNIQUE (slug)
)COMMENT='课程分类表' ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 动作分类表
CREATE TABLE IF NOT EXISTS exercise_categories (
	id INTEGER AUTO_INCREMENT NOT NULL, 
	name VARCHAR(50) NOT NULL COMMENT '分类名称', 
	slug VARCHAR(50) NOT NULL COMMENT '英文标识', 
	body_part VARCHAR(30) COMMENT '主要部位 胸/背/腿/肩/手臂/核心/全身', 
	sort_order INTEGER NOT NULL COMMENT '排序', 
	created_at DATETIME NOT NULL COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP, 
	updated_at DATETIME NOT NULL COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	UNIQUE (name), 
	UNIQUE (slug)
)COMMENT='动作分类表' ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 计划模板库
CREATE TABLE IF NOT EXISTS plan_templates (
	id INTEGER AUTO_INCREMENT NOT NULL, 
	name VARCHAR(100) NOT NULL COMMENT '模板名称', 
	category VARCHAR(30) NOT NULL COMMENT '分类 减脂/增肌/HIIT/新手', 
	goal VARCHAR(30) NOT NULL COMMENT '目标', 
	difficulty INTEGER NOT NULL COMMENT '难度 1-5', 
	cycle_type VARCHAR(20) NOT NULL COMMENT 'daily/weekly', 
	cycle_days INTEGER NOT NULL COMMENT '周期天数', 
	cover VARCHAR(255) COMMENT '封面', 
	description TEXT COMMENT '模板说明', 
	items_json TEXT COMMENT '模板动作明细(JSON)，轻量存储避免多表', 
	use_count INTEGER NOT NULL COMMENT '被使用次数', 
	is_official BOOL NOT NULL COMMENT '是否官方模板', 
	created_at DATETIME NOT NULL COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP, 
	updated_at DATETIME NOT NULL COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id)
)COMMENT='计划模板库' ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 验证码表
CREATE TABLE IF NOT EXISTS sms_codes (
	id INTEGER AUTO_INCREMENT NOT NULL, 
	target VARCHAR(120) NOT NULL COMMENT '手机号或邮箱', 
	code VARCHAR(10) NOT NULL COMMENT '验证码', 
	scene VARCHAR(30) NOT NULL COMMENT '用途 bind_phone/reset_password', 
	expires_at DATETIME NOT NULL COMMENT '过期时间', 
	used BOOL NOT NULL COMMENT '是否已使用', 
	created_at DATETIME NOT NULL COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP, 
	updated_at DATETIME NOT NULL COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id)
)COMMENT='验证码表' ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX ix_sms_codes_target ON sms_codes (target);

-- 用户表
CREATE TABLE IF NOT EXISTS users (
	id INTEGER AUTO_INCREMENT NOT NULL COMMENT '用户ID', 
	username VARCHAR(50) NOT NULL COMMENT '用户名', 
	password_hash VARCHAR(255) NOT NULL COMMENT '密码哈希', 
	nickname VARCHAR(50) COMMENT '昵称', 
	avatar VARCHAR(255) COMMENT '头像URL', 
	gender INTEGER NOT NULL COMMENT '性别 0未知 1男 2女', 
	birthday DATE COMMENT '生日', 
	height DOUBLE COMMENT '身高cm', 
	target_weight DOUBLE COMMENT '目标体重kg', 
	signature VARCHAR(200) COMMENT '个性签名', 
	phone VARCHAR(20) COMMENT '手机号', 
	email VARCHAR(120) COMMENT '邮箱', 
	city VARCHAR(50) COMMENT '城市', 
	points INTEGER NOT NULL COMMENT '总积分（决定等级）', 
	level INTEGER NOT NULL COMMENT '用户等级 1-10', 
	is_verified BOOL NOT NULL COMMENT '是否已实名认证', 
	is_disabled BOOL NOT NULL COMMENT '是否被封禁', 
	last_login_at DATETIME COMMENT '最后登录时间', 
	created_at DATETIME NOT NULL COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP, 
	updated_at DATETIME NOT NULL COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id)
)COMMENT='用户表' ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE UNIQUE INDEX ix_users_phone ON users (phone);
CREATE UNIQUE INDEX ix_users_email ON users (email);
CREATE UNIQUE INDEX ix_users_username ON users (username);

-- 身体数据记录表
CREATE TABLE IF NOT EXISTS body_metrics (
	id INTEGER AUTO_INCREMENT NOT NULL, 
	user_id INTEGER NOT NULL, 
	metric_date DATE NOT NULL COMMENT '记录日期', 
	weight FLOAT COMMENT '体重kg', 
	body_fat FLOAT COMMENT '体脂率%%', 
	muscle_mass FLOAT COMMENT '肌肉量kg', 
	waist FLOAT COMMENT '腰围cm', 
	chest FLOAT COMMENT '胸围cm', 
	hip FLOAT COMMENT '臀围cm', 
	note VARCHAR(200) COMMENT '备注', 
	created_at DATETIME NOT NULL COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP, 
	updated_at DATETIME NOT NULL COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_metric_user_date UNIQUE (user_id, metric_date), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
)COMMENT='身体数据记录表' ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX ix_body_metrics_metric_date ON body_metrics (metric_date);
CREATE INDEX ix_body_metrics_user_id ON body_metrics (user_id);

-- 每日签到记录
CREATE TABLE IF NOT EXISTS checkin_records (
	id INTEGER AUTO_INCREMENT NOT NULL, 
	user_id INTEGER NOT NULL COMMENT '用户ID', 
	checkin_date DATE NOT NULL COMMENT '签到日期', 
	streak INTEGER NOT NULL COMMENT '签到时连续天数', 
	points_awarded INTEGER NOT NULL COMMENT '本次获得积分', 
	created_at DATETIME NOT NULL COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP, 
	updated_at DATETIME NOT NULL COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_checkin_user_date UNIQUE (user_id, checkin_date), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
)COMMENT='每日签到记录' ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX ix_checkin_records_user_id ON checkin_records (user_id);
CREATE INDEX ix_checkin_records_checkin_date ON checkin_records (checkin_date);

-- 运动课程表
CREATE TABLE IF NOT EXISTS courses (
	id INTEGER AUTO_INCREMENT NOT NULL, 
	category_id INTEGER NOT NULL COMMENT '分类ID', 
	title VARCHAR(120) NOT NULL COMMENT '课程标题', 
	subtitle VARCHAR(200) COMMENT '副标题', 
	cover VARCHAR(255) COMMENT '封面图', 
	video_url VARCHAR(500) COMMENT '视频地址(m3u8/mp4)', 
	duration_min INTEGER NOT NULL COMMENT '时长(分钟)', 
	calories INTEGER NOT NULL COMMENT '预计消耗(千卡)', 
	difficulty INTEGER NOT NULL COMMENT '难度 1初级 2中级 3高级', 
	equipment VARCHAR(100) COMMENT '所需器械', 
	body_parts VARCHAR(100) COMMENT '锻炼部位，逗号分隔', 
	description TEXT COMMENT '课程介绍', 
	coach_name VARCHAR(50) COMMENT '教练名', 
	view_count INTEGER NOT NULL COMMENT '播放量', 
	favorite_count INTEGER NOT NULL COMMENT '收藏数', 
	rating_avg FLOAT NOT NULL COMMENT '平均评分', 
	rating_count INTEGER NOT NULL COMMENT '评分人数', 
	is_published BOOL NOT NULL COMMENT '是否上架', 
	sort_order INTEGER NOT NULL COMMENT '排序权重', 
	created_at DATETIME NOT NULL COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP, 
	updated_at DATETIME NOT NULL COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	FOREIGN KEY(category_id) REFERENCES course_categories (id)
)COMMENT='运动课程表' ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX ix_courses_is_published ON courses (is_published);
CREATE INDEX ix_courses_category_id ON courses (category_id);
CREATE INDEX ix_courses_difficulty ON courses (difficulty);

-- 动作库表
CREATE TABLE IF NOT EXISTS exercises (
	id INTEGER AUTO_INCREMENT NOT NULL, 
	category_id INTEGER NOT NULL COMMENT '分类ID', 
	name VARCHAR(100) NOT NULL COMMENT '动作名称', 
	name_en VARCHAR(100) COMMENT '英文名/别名，供搜索', 
	equipment VARCHAR(50) COMMENT '器械 杠铃/哑铃/自重/弹力带/器械', 
	difficulty INTEGER NOT NULL COMMENT '难度 1-5', 
	image_url VARCHAR(255) COMMENT '动作配图', 
	gif_url VARCHAR(255) COMMENT '动作动图/视频', 
	description TEXT COMMENT '动作讲解', 
	key_points TEXT COMMENT '发力要点', 
	common_mistakes TEXT COMMENT '易错提醒', 
	primary_muscles VARCHAR(120) COMMENT '主要发力肌群', 
	secondary_muscles VARCHAR(120) COMMENT '协同肌群', 
	tips TEXT COMMENT '呼吸与节奏提示', 
	keywords VARCHAR(255) COMMENT '搜索关键词，逗号分隔', 
	view_count INTEGER NOT NULL COMMENT '浏览数', 
	is_active BOOL NOT NULL COMMENT '是否启用', 
	created_at DATETIME NOT NULL COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP, 
	updated_at DATETIME NOT NULL COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	FOREIGN KEY(category_id) REFERENCES exercise_categories (id)
)COMMENT='动作库表' ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX ix_exercises_category_id ON exercises (category_id);
CREATE INDEX ix_exercises_name ON exercises (name);
CREATE INDEX ix_exercises_is_active ON exercises (is_active);
CREATE INDEX ix_exercises_difficulty ON exercises (difficulty);

-- 关注关系表
CREATE TABLE IF NOT EXISTS follows (
	id INTEGER AUTO_INCREMENT NOT NULL, 
	follower_id INTEGER NOT NULL COMMENT '关注者', 
	following_id INTEGER NOT NULL COMMENT '被关注者', 
	created_at DATETIME NOT NULL COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP, 
	updated_at DATETIME NOT NULL COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_follow UNIQUE (follower_id, following_id), 
	FOREIGN KEY(follower_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(following_id) REFERENCES users (id) ON DELETE CASCADE
)COMMENT='关注关系表' ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX ix_follows_following_id ON follows (following_id);
CREATE INDEX ix_follows_follower_id ON follows (follower_id);

-- 食物库表
CREATE TABLE IF NOT EXISTS foods (
	id INTEGER AUTO_INCREMENT NOT NULL, 
	name VARCHAR(100) NOT NULL COMMENT '食物名称', 
	category VARCHAR(30) NOT NULL COMMENT '分类 主食/肉蛋/蔬菜/水果/乳品/零食', 
	unit VARCHAR(20) NOT NULL COMMENT '计量单位描述', 
	calories FLOAT NOT NULL COMMENT '每100g热量(千卡)', 
	protein FLOAT NOT NULL COMMENT '蛋白质g', 
	fat FLOAT NOT NULL COMMENT '脂肪g', 
	carbohydrate FLOAT NOT NULL COMMENT '碳水g', 
	fiber FLOAT NOT NULL COMMENT '膳食纤维g', 
	sodium FLOAT NOT NULL COMMENT '钠mg', 
	is_common BOOL NOT NULL COMMENT '是否常用(前端快捷选择)', 
	created_by INTEGER COMMENT '自定义食物创建者', 
	created_at DATETIME NOT NULL COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP, 
	updated_at DATETIME NOT NULL COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
)COMMENT='食物库表' ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX ix_foods_category ON foods (category);
CREATE INDEX ix_foods_name ON foods (name);

-- 消息通知表
CREATE TABLE IF NOT EXISTS notifications (
	id INTEGER AUTO_INCREMENT NOT NULL, 
	user_id INTEGER NOT NULL COMMENT '接收人', 
	title VARCHAR(120) NOT NULL COMMENT '标题', 
	content TEXT NOT NULL COMMENT '正文', 
	notify_type VARCHAR(30) NOT NULL COMMENT '类型 system/plan/course/comment', 
	biz_id INTEGER COMMENT '关联业务ID', 
	is_read BOOL NOT NULL COMMENT '是否已读', 
	created_at DATETIME NOT NULL COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP, 
	updated_at DATETIME NOT NULL COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
)COMMENT='消息通知表' ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX ix_notifications_is_read ON notifications (is_read);
CREATE INDEX ix_notifications_user_id ON notifications (user_id);

-- 训练计划表
CREATE TABLE IF NOT EXISTS plans (
	id INTEGER AUTO_INCREMENT NOT NULL, 
	user_id INTEGER NOT NULL COMMENT '所属用户', 
	name VARCHAR(100) NOT NULL COMMENT '计划名称', 
	description TEXT COMMENT '计划说明', 
	goal VARCHAR(30) NOT NULL COMMENT '目标 增肌/减脂/塑形/康复/keep_fit', 
	cycle_type VARCHAR(20) NOT NULL COMMENT '周期类型 daily/weekly', 
	cycle_days INTEGER NOT NULL COMMENT '一个周期天数', 
	cover VARCHAR(255) COMMENT '封面图', 
	is_public BOOL NOT NULL COMMENT '是否公开分享', 
	is_template BOOL NOT NULL COMMENT '是否另存为模板', 
	favorite_count INTEGER NOT NULL COMMENT '被收藏次数', 
	status VARCHAR(20) NOT NULL COMMENT 'active/archived', 
	created_at DATETIME NOT NULL COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP, 
	updated_at DATETIME NOT NULL COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
)COMMENT='训练计划表' ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX ix_plans_user_id ON plans (user_id);

-- 实名认证表
CREATE TABLE IF NOT EXISTS real_name_auths (
	id INTEGER AUTO_INCREMENT NOT NULL, 
	user_id INTEGER NOT NULL, 
	real_name VARCHAR(50) NOT NULL COMMENT '真实姓名', 
	id_card VARCHAR(30) NOT NULL COMMENT '身份证号（存储时脱敏）', 
	status VARCHAR(20) NOT NULL COMMENT 'pending/approved/rejected', 
	reject_reason VARCHAR(200) COMMENT '驳回原因', 
	reviewed_at DATETIME COMMENT '审核时间', 
	created_at DATETIME NOT NULL COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP, 
	updated_at DATETIME NOT NULL COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_realname_user UNIQUE (user_id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
)COMMENT='实名认证表' ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX ix_real_name_auths_status ON real_name_auths (status);
CREATE INDEX ix_real_name_auths_user_id ON real_name_auths (user_id);

-- 课程评论表
CREATE TABLE IF NOT EXISTS course_comments (
	id INTEGER AUTO_INCREMENT NOT NULL, 
	course_id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	parent_id INTEGER COMMENT '父评论ID', 
	content TEXT NOT NULL COMMENT '评论内容', 
	like_count INTEGER NOT NULL COMMENT '点赞数', 
	status VARCHAR(20) NOT NULL COMMENT 'pending/approved/rejected 审核状态', 
	created_at DATETIME NOT NULL COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP, 
	updated_at DATETIME NOT NULL COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	FOREIGN KEY(course_id) REFERENCES courses (id) ON DELETE CASCADE, 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(parent_id) REFERENCES course_comments (id) ON DELETE CASCADE
)COMMENT='课程评论表' ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX ix_course_comments_status ON course_comments (status);
CREATE INDEX ix_course_comments_course_id ON course_comments (course_id);
CREATE INDEX ix_course_comments_user_id ON course_comments (user_id);

-- 课程收藏表
CREATE TABLE IF NOT EXISTS course_favorites (
	id INTEGER AUTO_INCREMENT NOT NULL, 
	user_id INTEGER NOT NULL, 
	course_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP, 
	updated_at DATETIME NOT NULL COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_course_fav UNIQUE (user_id, course_id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(course_id) REFERENCES courses (id) ON DELETE CASCADE
)COMMENT='课程收藏表' ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX ix_course_favorites_course_id ON course_favorites (course_id);
CREATE INDEX ix_course_favorites_user_id ON course_favorites (user_id);

-- 课程评分表
CREATE TABLE IF NOT EXISTS course_ratings (
	id INTEGER AUTO_INCREMENT NOT NULL, 
	user_id INTEGER NOT NULL, 
	course_id INTEGER NOT NULL, 
	score INTEGER NOT NULL COMMENT '评分 1-5', 
	created_at DATETIME NOT NULL COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP, 
	updated_at DATETIME NOT NULL COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_course_rating UNIQUE (user_id, course_id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(course_id) REFERENCES courses (id) ON DELETE CASCADE
)COMMENT='课程评分表' ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX ix_course_ratings_course_id ON course_ratings (course_id);
CREATE INDEX ix_course_ratings_user_id ON course_ratings (user_id);

-- 饮食记录表
CREATE TABLE IF NOT EXISTS diet_records (
	id INTEGER AUTO_INCREMENT NOT NULL, 
	user_id INTEGER NOT NULL, 
	diet_date DATE NOT NULL COMMENT '日期', 
	meal_type VARCHAR(20) NOT NULL COMMENT 'breakfast/lunch/dinner/snack', 
	food_id INTEGER COMMENT '食物ID', 
	food_name VARCHAR(100) NOT NULL COMMENT '食物名称快照', 
	amount_g FLOAT NOT NULL COMMENT '食用量(克)', 
	calories FLOAT NOT NULL COMMENT '本次摄入热量(千卡)', 
	protein FLOAT NOT NULL COMMENT '蛋白质g', 
	fat FLOAT NOT NULL COMMENT '脂肪g', 
	carbohydrate FLOAT NOT NULL COMMENT '碳水g', 
	note VARCHAR(200) COMMENT '备注', 
	created_at DATETIME NOT NULL COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP, 
	updated_at DATETIME NOT NULL COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(food_id) REFERENCES foods (id) ON DELETE SET NULL
)COMMENT='饮食记录表' ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX ix_diet_records_diet_date ON diet_records (diet_date);
CREATE INDEX ix_diet_records_user_id ON diet_records (user_id);

-- 计划打卡表
CREATE TABLE IF NOT EXISTS plan_checkins (
	id INTEGER AUTO_INCREMENT NOT NULL, 
	user_id INTEGER NOT NULL, 
	plan_id INTEGER NOT NULL, 
	checkin_date DATE NOT NULL COMMENT '打卡日期', 
	day_index INTEGER NOT NULL COMMENT '完成的是周期第几天', 
	completed BOOL NOT NULL COMMENT '是否完成', 
	note VARCHAR(200) COMMENT '打卡备注', 
	created_at DATETIME NOT NULL COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP, 
	updated_at DATETIME NOT NULL COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_plan_checkin UNIQUE (user_id, plan_id, checkin_date), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(plan_id) REFERENCES plans (id) ON DELETE CASCADE
)COMMENT='计划打卡表' ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX ix_plan_checkins_checkin_date ON plan_checkins (checkin_date);
CREATE INDEX ix_plan_checkins_plan_id ON plan_checkins (plan_id);
CREATE INDEX ix_plan_checkins_user_id ON plan_checkins (user_id);

-- 计划收藏表
CREATE TABLE IF NOT EXISTS plan_favorites (
	id INTEGER AUTO_INCREMENT NOT NULL, 
	user_id INTEGER NOT NULL, 
	plan_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP, 
	updated_at DATETIME NOT NULL COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_plan_fav UNIQUE (user_id, plan_id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(plan_id) REFERENCES plans (id) ON DELETE CASCADE
)COMMENT='计划收藏表' ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX ix_plan_favorites_user_id ON plan_favorites (user_id);
CREATE INDEX ix_plan_favorites_plan_id ON plan_favorites (plan_id);

-- 计划动作明细表
CREATE TABLE IF NOT EXISTS plan_items (
	id INTEGER AUTO_INCREMENT NOT NULL, 
	plan_id INTEGER NOT NULL, 
	exercise_id INTEGER COMMENT '动作ID', 
	day_index INTEGER NOT NULL COMMENT '周期内第几天，从 1 开始', 
	sort_order INTEGER NOT NULL COMMENT '当天排序', 
	sets INTEGER NOT NULL COMMENT '组数', 
	reps INTEGER NOT NULL COMMENT '每组次数', 
	weight DOUBLE COMMENT '建议重量kg', 
	rest_seconds INTEGER NOT NULL COMMENT '组间休息秒数', 
	duration_min INTEGER COMMENT '有氧时长分钟', 
	note VARCHAR(200) COMMENT '备注', 
	created_at DATETIME NOT NULL COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP, 
	updated_at DATETIME NOT NULL COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	FOREIGN KEY(plan_id) REFERENCES plans (id) ON DELETE CASCADE, 
	FOREIGN KEY(exercise_id) REFERENCES exercises (id) ON DELETE SET NULL
)COMMENT='计划动作明细表' ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX ix_plan_items_plan_id ON plan_items (plan_id);

-- 计划提醒表
CREATE TABLE IF NOT EXISTS plan_reminders (
	id INTEGER AUTO_INCREMENT NOT NULL, 
	user_id INTEGER NOT NULL, 
	plan_id INTEGER NOT NULL, 
	remind_time TIME NOT NULL COMMENT '每天提醒时间', 
	weekdays VARCHAR(20) NOT NULL COMMENT '周几提醒，逗号分隔', 
	enabled BOOL NOT NULL COMMENT '是否启用', 
	last_fired_at DATETIME COMMENT '上次触发时间', 
	created_at DATETIME NOT NULL COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP, 
	updated_at DATETIME NOT NULL COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(plan_id) REFERENCES plans (id) ON DELETE CASCADE
)COMMENT='计划提醒表' ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX ix_plan_reminders_plan_id ON plan_reminders (plan_id);
CREATE INDEX ix_plan_reminders_user_id ON plan_reminders (user_id);

-- 计划分享表
CREATE TABLE IF NOT EXISTS plan_shares (
	id INTEGER AUTO_INCREMENT NOT NULL, 
	plan_id INTEGER NOT NULL, 
	share_code VARCHAR(20) NOT NULL COMMENT '分享码', 
	expires_at DATETIME COMMENT '过期时间，空表示永久', 
	view_count INTEGER NOT NULL COMMENT '被查看次数', 
	created_at DATETIME NOT NULL COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP, 
	updated_at DATETIME NOT NULL COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	FOREIGN KEY(plan_id) REFERENCES plans (id) ON DELETE CASCADE
)COMMENT='计划分享表' ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE UNIQUE INDEX ix_plan_shares_share_code ON plan_shares (share_code);
CREATE INDEX ix_plan_shares_plan_id ON plan_shares (plan_id);

-- 运动记录表
CREATE TABLE IF NOT EXISTS workout_records (
	id INTEGER AUTO_INCREMENT NOT NULL, 
	user_id INTEGER NOT NULL COMMENT '用户ID', 
	plan_id INTEGER COMMENT '关联计划', 
	course_id INTEGER COMMENT '关联课程', 
	workout_date DATE NOT NULL COMMENT '训练日期', 
	workout_type VARCHAR(30) NOT NULL COMMENT '类型 strength/cardio/stretch/hiit/yoga', 
	title VARCHAR(100) COMMENT '本次训练标题', 
	duration_min INTEGER NOT NULL COMMENT '总时长(分钟)', 
	calories FLOAT NOT NULL COMMENT '消耗卡路里', 
	feeling INTEGER NOT NULL COMMENT '主观强度 1-5', 
	note TEXT COMMENT '训练备注', 
	created_at DATETIME NOT NULL COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP, 
	updated_at DATETIME NOT NULL COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(plan_id) REFERENCES plans (id) ON DELETE SET NULL, 
	FOREIGN KEY(course_id) REFERENCES courses (id) ON DELETE SET NULL
)COMMENT='运动记录表' ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX ix_workout_records_workout_date ON workout_records (workout_date);
CREATE INDEX ix_workout_records_user_id ON workout_records (user_id);

-- 评论点赞表
CREATE TABLE IF NOT EXISTS course_comment_likes (
	id INTEGER AUTO_INCREMENT NOT NULL, 
	user_id INTEGER NOT NULL, 
	comment_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP, 
	updated_at DATETIME NOT NULL COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_comment_like UNIQUE (user_id, comment_id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(comment_id) REFERENCES course_comments (id) ON DELETE CASCADE
)COMMENT='评论点赞表' ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX ix_course_comment_likes_user_id ON course_comment_likes (user_id);
CREATE INDEX ix_course_comment_likes_comment_id ON course_comment_likes (comment_id);

-- 社区动态表
CREATE TABLE IF NOT EXISTS posts (
	id INTEGER AUTO_INCREMENT NOT NULL, 
	user_id INTEGER NOT NULL COMMENT '发布者', 
	content TEXT NOT NULL COMMENT '文字内容', 
	images TEXT COMMENT '图片URL，逗号分隔', 
	topic VARCHAR(50) COMMENT '话题标签', 
	location VARCHAR(100) COMMENT '位置', 
	workout_record_id INTEGER COMMENT '关联训练记录', 
	like_count INTEGER NOT NULL COMMENT '点赞数', 
	comment_count INTEGER NOT NULL COMMENT '评论数', 
	view_count INTEGER NOT NULL COMMENT '浏览数', 
	is_top BOOL NOT NULL COMMENT '是否置顶', 
	is_visible BOOL NOT NULL COMMENT '是否可见(管理员可隐藏)', 
	created_at DATETIME NOT NULL COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP, 
	updated_at DATETIME NOT NULL COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(workout_record_id) REFERENCES workout_records (id) ON DELETE SET NULL
)COMMENT='社区动态表' ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX ix_posts_user_id ON posts (user_id);

-- 运动组次明细表
CREATE TABLE IF NOT EXISTS workout_sets (
	id INTEGER AUTO_INCREMENT NOT NULL, 
	record_id INTEGER NOT NULL, 
	exercise_id INTEGER COMMENT '动作ID', 
	exercise_name VARCHAR(100) COMMENT '动作名快照(动作被删也能显示)', 
	sort_order INTEGER NOT NULL COMMENT '动作顺序', 
	set_index INTEGER NOT NULL COMMENT '第几组', 
	weight FLOAT NOT NULL COMMENT '重量kg', 
	reps INTEGER NOT NULL COMMENT '次数', 
	duration_sec INTEGER COMMENT '有氧/静力动作时长(秒)', 
	distance_km FLOAT COMMENT '跑步距离(公里)', 
	note VARCHAR(200) COMMENT '备注', 
	created_at DATETIME NOT NULL COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP, 
	updated_at DATETIME NOT NULL COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	FOREIGN KEY(record_id) REFERENCES workout_records (id) ON DELETE CASCADE, 
	FOREIGN KEY(exercise_id) REFERENCES exercises (id) ON DELETE SET NULL
)COMMENT='运动组次明细表' ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX ix_workout_sets_record_id ON workout_sets (record_id);

-- 动态评论表
CREATE TABLE IF NOT EXISTS post_comments (
	id INTEGER AUTO_INCREMENT NOT NULL, 
	post_id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	parent_id INTEGER COMMENT '父评论', 
	reply_to_user_id INTEGER COMMENT '回复谁', 
	content TEXT NOT NULL COMMENT '评论内容', 
	like_count INTEGER NOT NULL COMMENT '点赞数', 
	created_at DATETIME NOT NULL COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP, 
	updated_at DATETIME NOT NULL COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	FOREIGN KEY(post_id) REFERENCES posts (id) ON DELETE CASCADE, 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(parent_id) REFERENCES post_comments (id) ON DELETE CASCADE, 
	FOREIGN KEY(reply_to_user_id) REFERENCES users (id) ON DELETE SET NULL
)COMMENT='动态评论表' ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX ix_post_comments_user_id ON post_comments (user_id);
CREATE INDEX ix_post_comments_post_id ON post_comments (post_id);

-- 动态点赞表
CREATE TABLE IF NOT EXISTS post_likes (
	id INTEGER AUTO_INCREMENT NOT NULL, 
	user_id INTEGER NOT NULL, 
	post_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP, 
	updated_at DATETIME NOT NULL COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_post_like UNIQUE (user_id, post_id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(post_id) REFERENCES posts (id) ON DELETE CASCADE
)COMMENT='动态点赞表' ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX ix_post_likes_post_id ON post_likes (post_id);
CREATE INDEX ix_post_likes_user_id ON post_likes (user_id);

SET FOREIGN_KEY_CHECKS = 1;
