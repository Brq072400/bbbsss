"""社区模块接口。

包含：动态发布/列表/详情/删除、关注流、推荐流、点赞、评论（含回复）、
关注关系、用户主页、粉丝/关注列表、用户搜索。

设计要点：
- 所有用户侧写操作都只允许操作「自己的数据」，越权返回 403；
- 匿名用户（OptionalUser 为空）也能浏览动态，只是 is_liked / is_following 恒为 False；
- Post.images 在数据库里是逗号分隔字符串，出参统一转成数组（见 schemas.community）。
"""
from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, DbSession, OptionalUser
from app.core.pagination import PageParams, PageResult, page_params, paginate
from app.core.response import BadRequestError, ConflictError, ForbiddenError, NotFoundError, ok
from app.models.community import Follow, Post, PostComment, PostLike
from app.models.user import User
from app.schemas.community import (
    AuthorBrief,
    CommentCreateRequest,
    CommentOut,
    CommentReplyOut,
    FeedPageOut,
    FollowResultOut,
    LikeResultOut,
    PostCreateRequest,
    PostDetailOut,
    PostOut,
    UserCardOut,
    UserProfileOut,
    join_images,
    split_images,
)

router = APIRouter(prefix="/community", tags=["社区"])

# 推荐流参数：参与排序的候选池大小、最终条数、时间衰减半衰期与权重
RECOMMEND_LIMIT = 20
RECOMMEND_CANDIDATES = 300
DECAY_HOURS = 72.0
DECAY_WEIGHT = 5.0


# ---------------------------------------------------------------- 内部工具
def _author_brief(user: User | None) -> AuthorBrief | None:
    """把 User 转成作者简要信息。

    参数:
        user: 用户 ORM 对象，可为 None（数据被删除时）。
    返回:
        AuthorBrief 或 None。
    """
    if user is None:
        return None
    return AuthorBrief(
        id=user.id,
        username=user.username,
        nickname=user.nickname,
        display_name=user.nickname or user.username,
        avatar=user.avatar,
        level=user.level or 1,
    )


def _user_card(user: User, is_following: bool = False) -> UserCardOut:
    """把 User 转成用户卡片（粉丝/关注列表、搜索结果用）。

    参数:
        user: 用户 ORM 对象。
        is_following: 当前登录用户是否已关注该用户。
    返回:
        UserCardOut。
    """
    return UserCardOut(
        id=user.id,
        username=user.username,
        nickname=user.nickname,
        display_name=user.nickname or user.username,
        avatar=user.avatar,
        signature=user.signature,
        level=user.level or 1,
        is_verified=bool(user.is_verified),
        is_following=is_following,
    )


def _post_out(post: Post, is_liked: bool = False) -> PostOut:
    """把 Post 转成列表用的出参。

    参数:
        post: 动态 ORM 对象（Post.user 关系已 joined 加载）。
        is_liked: 当前登录用户是否已点赞。
    返回:
        PostOut。
    """
    return PostOut(
        id=post.id,
        user_id=post.user_id,
        content=post.content,
        images=split_images(post.images),
        topic=post.topic,
        location=post.location,
        like_count=post.like_count or 0,
        comment_count=post.comment_count or 0,
        view_count=post.view_count or 0,
        is_top=bool(post.is_top),
        is_visible=bool(post.is_visible),
        created_at=post.created_at,
        author=_author_brief(post.user),
        is_liked=is_liked,
    )


def _post_detail_out(post: Post, is_liked: bool = False, is_followed: bool = False) -> PostDetailOut:
    """把 Post 转成详情出参（比列表多一个「是否已关注作者」）。

    参数:
        post: 动态 ORM 对象。
        is_liked: 当前登录用户是否已点赞。
        is_followed: 当前登录用户是否已关注作者。
    返回:
        PostDetailOut。
    """
    base = _post_out(post, is_liked=is_liked)
    return PostDetailOut(**base.model_dump(), is_followed=is_followed)


def _comment_reply_out(comment: PostComment, reply_to_nickname: str | None = None) -> CommentReplyOut:
    """把评论转成「回复」出参。

    参数:
        comment: 评论 ORM 对象。
        reply_to_nickname: 被回复用户的展示名。
    返回:
        CommentReplyOut。
    """
    return CommentReplyOut(
        id=comment.id,
        post_id=comment.post_id,
        parent_id=comment.parent_id,
        user_id=comment.user_id,
        content=comment.content,
        reply_to_user_id=comment.reply_to_user_id,
        reply_to_nickname=reply_to_nickname,
        created_at=comment.created_at,
        author=_author_brief(comment.user),
    )


def _comment_out(comment: PostComment, reply_to_nickname: str | None = None) -> CommentOut:
    """把评论转成「一级评论」出参（replies / reply_count 由调用方再补）。

    参数:
        comment: 评论 ORM 对象。
        reply_to_nickname: 被回复用户的展示名。
    返回:
        CommentOut。
    """
    reply = _comment_reply_out(comment, reply_to_nickname)
    return CommentOut(**reply.model_dump(), like_count=comment.like_count or 0)


def _get_post(db: Session, post_id: int, current: User | None = None) -> Post:
    """取一条可见动态，不存在或已被隐藏则抛 404（作者本人仍可看到自己的隐藏动态）。

    参数:
        db: 数据库会话。
        post_id: 动态ID。
        current: 当前登录用户，可为 None。
    返回:
        Post ORM 对象。
    """
    post = db.get(Post, post_id)
    if post is None:
        raise NotFoundError("动态不存在")
    if not post.is_visible and (current is None or post.user_id != current.id):
        raise NotFoundError("动态不存在或已被隐藏")
    return post


def _liked_post_ids(db: Session, user_id: int | None, post_ids: list[int]) -> set[int]:
    """批量查询「我已点赞」的动态ID集合，避免逐条查询造成 N+1。

    参数:
        db: 数据库会话。
        user_id: 当前登录用户ID，未登录传 None。
        post_ids: 动态ID列表。
    返回:
        已点赞的动态ID集合。
    """
    if not user_id or not post_ids:
        return set()
    rows = db.scalars(select(PostLike.post_id).where(PostLike.user_id == user_id, PostLike.post_id.in_(post_ids)))
    return set(rows.all())


def _following_ids(db: Session, follower_id: int | None, target_ids: list[int]) -> set[int]:
    """批量查询「我关注了列表里的哪些人」。

    参数:
        db: 数据库会话。
        follower_id: 当前登录用户ID，未登录传 None。
        target_ids: 待检查的用户ID列表。
    返回:
        我已关注的用户ID集合。
    """
    if not follower_id or not target_ids:
        return set()
    rows = db.scalars(
        select(Follow.following_id).where(Follow.follower_id == follower_id, Follow.following_id.in_(target_ids))
    )
    return set(rows.all())


def _is_following(db: Session, follower_id: int | None, target_id: int) -> bool:
    """判断 follower 是否关注了 target（自己关注自己恒为 False）。"""
    if not follower_id or follower_id == target_id:
        return False
    return db.scalar(select(Follow.id).where(Follow.follower_id == follower_id, Follow.following_id == target_id)) is not None


def _count_followers(db: Session, user_id: int) -> int:
    """统计某用户的粉丝数。"""
    return int(db.scalar(select(func.count()).select_from(Follow).where(Follow.following_id == user_id)) or 0)


def _recommend_posts(db: Session, limit: int = RECOMMEND_LIMIT) -> list[Post]:
    """推荐算法实现，返回按热度排序的动态列表。

    算法说明（热度分 = 互动分 + 时间衰减）：
        score = like_count * 2 + comment_count * 3 + DECAY_WEIGHT * exp(-age_hours / DECAY_HOURS)

    1. 互动分：点赞权重 2、评论权重 3（评论成本更高，权重更高）；
    2. 时间衰减：新动态额外加分，最高 +5 分，之后按 72 小时为时间常数指数衰减，
       即 72 小时前发布的动态只能拿到约 37% 的加成、144 小时前约 13%，避免「老爆款」长期霸榜；
    3. 为了不把全表拉进内存，先按时间倒序取最近 RECOMMEND_CANDIDATES 条可见动态做候选池，
       在 Python 里算分排序后取前 limit 条（跨数据库通用，SQLite/MySQL 行为一致）。

    参数:
        db: 数据库会话。
        limit: 返回条数，默认 20。
    返回:
        动态 ORM 对象列表，按热度分从高到低。
    """
    stmt = (
        select(Post)
        .where(Post.is_visible.is_(True))
        .order_by(Post.created_at.desc(), Post.id.desc())
        .limit(RECOMMEND_CANDIDATES)
    )
    candidates = list(db.scalars(stmt).all())
    now = datetime.now()
    scored: list[tuple[float, Post]] = []
    for post in candidates:
        interaction = (post.like_count or 0) * 2 + (post.comment_count or 0) * 3
        created_at = post.created_at or now
        age_hours = max((now - created_at).total_seconds() / 3600.0, 0.0)
        decay = DECAY_WEIGHT * math.exp(-age_hours / DECAY_HOURS)
        scored.append((interaction + decay, post))
    scored.sort(key=lambda item: (-item[0], -item[1].id))
    return [post for _, post in scored[:limit]]


# ---------------------------------------------------------------- 动态
@router.post("/posts", summary="发布动态")
def create_post(req: PostCreateRequest, db: DbSession, current: CurrentUser) -> dict[str, Any]:
    """发布一条社区动态。

    参数:
        req: 动态内容、图片URL列表、话题、位置。
        db: 数据库会话。
        current: 当前登录用户（作者）。
    返回:
        统一响应，data 为新建动态的 PostOut（含作者信息）。
    """
    post = Post(
        user_id=current.id,
        content=req.content,
        images=join_images(req.images),
        topic=req.topic,
        location=req.location,
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return ok(_post_out(post))


@router.get("/posts", summary="动态列表（分页）")
def list_posts(
    db: DbSession,
    current: OptionalUser,
    params: PageParams = Depends(page_params),
    sort: Literal["latest", "hot"] = Query("latest", description="latest 最新 / hot 最热"),
) -> dict[str, Any]:
    """分页获取可见动态列表。

    参数:
        params: 分页参数（page / page_size）。
        sort: latest 按发布时间倒序；hot 按点赞数、评论数倒序。
        db: 数据库会话。
        current: 可选登录用户，用于计算「我是否已点赞」。
    返回:
        统一响应，data 为 PageResult[PostOut]。
    """
    stmt = select(Post).where(Post.is_visible.is_(True))
    if sort == "hot":
        stmt = stmt.order_by(
            Post.is_top.desc(),
            Post.like_count.desc(),
            Post.comment_count.desc(),
            Post.created_at.desc(),
            Post.id.desc(),
        )
    else:
        stmt = stmt.order_by(Post.is_top.desc(), Post.created_at.desc(), Post.id.desc())
    rows, total = paginate(db, stmt, params)
    liked = _liked_post_ids(db, current.id if current else None, [p.id for p in rows])
    items = [_post_out(post, is_liked=post.id in liked) for post in rows]
    return ok(PageResult.build(items, total, params))


@router.get("/posts/{post_id}", summary="动态详情")
def get_post(post_id: int, db: DbSession, current: OptionalUser) -> dict[str, Any]:
    """查看动态详情，同时把浏览数 +1。

    参数:
        post_id: 动态ID。
        db: 数据库会话。
        current: 可选登录用户（作者本人可查看自己已隐藏的动态）。
    返回:
        统一响应，data 为 PostDetailOut（作者信息、图片数组、点赞状态、评论数、是否已关注作者）。
    """
    post = _get_post(db, post_id, current)
    post.view_count = (post.view_count or 0) + 1
    db.commit()
    db.refresh(post)
    liked = _liked_post_ids(db, current.id if current else None, [post.id])
    return ok(
        _post_detail_out(
            post,
            is_liked=post.id in liked,
            is_followed=_is_following(db, current.id if current else None, post.user_id),
        )
    )


@router.delete("/posts/{post_id}", summary="删除自己的动态")
def delete_post(post_id: int, db: DbSession, current: CurrentUser) -> dict[str, Any]:
    """删除自己的动态（连带删除其点赞与评论）。

    参数:
        post_id: 动态ID。
        db: 数据库会话。
        current: 当前登录用户（必须是作者本人）。
    返回:
        统一响应，data 为删除结果。
    """
    post = _get_post(db, post_id, current)
    if post.user_id != current.id:
        raise ForbiddenError("只能删除自己的动态")
    # 显式清理点赞与评论，兼容未开启数据库级级联的环境
    db.execute(delete(PostLike).where(PostLike.post_id == post.id))
    db.execute(delete(PostComment).where(PostComment.post_id == post.id))
    db.delete(post)
    db.commit()
    return ok({"post_id": post_id, "deleted": True})


# ---------------------------------------------------------------- 关注流 / 推荐
@router.get("/feed", summary="关注的人发布的动态")
def get_feed(db: DbSession, current: CurrentUser, params: PageParams = Depends(page_params)) -> dict[str, Any]:
    """分页获取我关注的人发布的动态（按时间倒序）。

    参数:
        params: 分页参数。
        db: 数据库会话。
        current: 当前登录用户。
    返回:
        统一响应，data 为 FeedPageOut；若当前用户没有关注任何人，
        则返回推荐动态并置 empty=True，提示前端展示引导文案。
    """
    following_ids = list(db.scalars(select(Follow.following_id).where(Follow.follower_id == current.id)).all())
    if not following_ids:
        posts = _recommend_posts(db, limit=RECOMMEND_LIMIT)
        liked = _liked_post_ids(db, current.id, [p.id for p in posts])
        items = [_post_out(post, is_liked=post.id in liked) for post in posts]
        page = FeedPageOut.build(items, len(items), params)
        page.empty = True
        return ok(page, message="你还没有关注任何人，以下为推荐动态")

    stmt = (
        select(Post)
        .where(Post.user_id.in_(following_ids), Post.is_visible.is_(True))
        .order_by(Post.created_at.desc(), Post.id.desc())
    )
    rows, total = paginate(db, stmt, params)
    liked = _liked_post_ids(db, current.id, [p.id for p in rows])
    items = [_post_out(post, is_liked=post.id in liked) for post in rows]
    page = FeedPageOut.build(items, total, params)
    page.empty = False
    return ok(page)


@router.get("/recommend", summary="推荐动态")
def recommend_posts(db: DbSession, current: OptionalUser) -> dict[str, Any]:
    """获取推荐动态（最多 20 条）。

    排序算法：热度分 = 点赞数*2 + 评论数*3 + 时间衰减（详见 _recommend_posts 的说明）。

    参数:
        db: 数据库会话。
        current: 可选登录用户，用于计算「我是否已点赞」。
    返回:
        统一响应，data 为 PostOut 列表。
    """
    posts = _recommend_posts(db, limit=RECOMMEND_LIMIT)
    liked = _liked_post_ids(db, current.id if current else None, [p.id for p in posts])
    items = [_post_out(post, is_liked=post.id in liked) for post in posts]
    return ok(items)


# ---------------------------------------------------------------- 点赞
@router.post("/posts/{post_id}/like", summary="点赞动态")
def like_post(post_id: int, db: DbSession, current: CurrentUser) -> dict[str, Any]:
    """给动态点赞。

    参数:
        post_id: 动态ID。
        db: 数据库会话。
        current: 当前登录用户。
    返回:
        统一响应，data 为 LikeResultOut（最新点赞数）；重复点赞抛 409。
    """
    post = _get_post(db, post_id, current)
    exists = db.scalar(select(PostLike.id).where(PostLike.user_id == current.id, PostLike.post_id == post.id))
    if exists is not None:
        raise ConflictError("你已经点过赞了")
    db.add(PostLike(user_id=current.id, post_id=post.id))
    post.like_count = (post.like_count or 0) + 1
    db.commit()
    return ok(LikeResultOut(post_id=post.id, like_count=post.like_count, is_liked=True))


@router.delete("/posts/{post_id}/like", summary="取消点赞")
def unlike_post(post_id: int, db: DbSession, current: CurrentUser) -> dict[str, Any]:
    """取消点赞。

    参数:
        post_id: 动态ID。
        db: 数据库会话。
        current: 当前登录用户。
    返回:
        统一响应，data 为 LikeResultOut（点赞数不会小于 0）。
    """
    post = _get_post(db, post_id, current)
    like = db.scalar(select(PostLike).where(PostLike.user_id == current.id, PostLike.post_id == post.id))
    if like is None:
        raise NotFoundError("你还没有点赞该动态")
    db.delete(like)
    post.like_count = max(0, (post.like_count or 0) - 1)
    db.commit()
    return ok(LikeResultOut(post_id=post.id, like_count=post.like_count, is_liked=False))


# ---------------------------------------------------------------- 评论
@router.post("/posts/{post_id}/comment", summary="发表评论/回复")
def create_comment(
    post_id: int, req: CommentCreateRequest, db: DbSession, current: CurrentUser
) -> dict[str, Any]:
    """给动态发表评论，支持回复某条评论。

    两级结构约定：回复「回复」时，parent_id 统一归到根评论，
    被回复人写入 reply_to_user_id，前端即可渲染 「回复 @某人」。

    参数:
        post_id: 动态ID。
        req: 评论内容与可选父评论ID。
        db: 数据库会话。
        current: 当前登录用户。
    返回:
        统一响应，data 为新建评论的 CommentOut。
    """
    post = _get_post(db, post_id, current)
    parent: PostComment | None = None
    reply_to_user_id: int | None = None
    if req.parent_id is not None:
        parent = db.get(PostComment, req.parent_id)
        if parent is None or parent.post_id != post.id:
            raise BadRequestError("父评论不存在或不属于该动态")
        reply_to_user_id = parent.user_id
        if parent.parent_id is not None:
            # 回复的回复：统一挂到根评论下，保证评论树只有两级
            root = db.get(PostComment, parent.parent_id)
            if root is None or root.post_id != post.id:
                raise BadRequestError("父评论不存在或不属于该动态")
            parent = root

    comment = PostComment(
        post_id=post.id,
        user_id=current.id,
        parent_id=parent.id if parent is not None else None,
        reply_to_user_id=reply_to_user_id,
        content=req.content,
    )
    db.add(comment)
    post.comment_count = (post.comment_count or 0) + 1
    db.commit()
    db.refresh(comment)
    nickname = None
    if comment.reply_to_user_id:
        target = db.get(User, comment.reply_to_user_id)
        nickname = (target.nickname or target.username) if target else None
    return ok(_comment_out(comment, nickname))


@router.get("/posts/{post_id}/comments", summary="评论列表（分页）")
def list_comments(post_id: int, db: DbSession, params: PageParams = Depends(page_params)) -> dict[str, Any]:
    """分页获取动态的一级评论，每条评论带最多 3 条回复与回复总数。

    参数:
        post_id: 动态ID。
        params: 分页参数（对一级评论分页）。
        db: 数据库会话。
    返回:
        统一响应，data 为 PageResult[CommentOut]。
    """
    _get_post(db, post_id)
    stmt = (
        select(PostComment)
        .where(PostComment.post_id == post_id, PostComment.parent_id.is_(None))
        .order_by(PostComment.created_at.asc(), PostComment.id.asc())
    )
    roots, total = paginate(db, stmt, params)
    root_ids = [c.id for c in roots]

    reply_map: dict[int, list[PostComment]] = {rid: [] for rid in root_ids}
    reply_counts: dict[int, int] = {rid: 0 for rid in root_ids}
    if root_ids:
        replies = db.scalars(
            select(PostComment)
            .where(PostComment.parent_id.in_(root_ids))
            .order_by(PostComment.created_at.asc(), PostComment.id.asc())
        ).all()
        for reply in replies:
            parent_id = reply.parent_id or 0
            reply_counts[parent_id] = reply_counts.get(parent_id, 0) + 1
            preview = reply_map.setdefault(parent_id, [])
            if len(preview) < 3:
                preview.append(reply)

    # 批量取「被回复人」展示名，避免逐条查询
    reply_to_ids = {
        c.reply_to_user_id
        for c in [*roots, *[r for group in reply_map.values() for r in group]]
        if c.reply_to_user_id
    }
    nick_map: dict[int, str] = {}
    if reply_to_ids:
        for user in db.scalars(select(User).where(User.id.in_(reply_to_ids))).all():
            nick_map[user.id] = user.nickname or user.username

    items: list[CommentOut] = []
    for root in roots:
        out = _comment_out(root, nick_map.get(root.reply_to_user_id or 0))
        out.replies = [_comment_reply_out(r, nick_map.get(r.reply_to_user_id or 0)) for r in reply_map.get(root.id, [])]
        out.reply_count = reply_counts.get(root.id, 0)
        items.append(out)
    return ok(PageResult.build(items, total, params))


@router.delete("/comment/{comment_id}", summary="删除自己的评论")
def delete_comment(comment_id: int, db: DbSession, current: CurrentUser) -> dict[str, Any]:
    """删除自己发表的评论（连带删除其下的回复）。

    参数:
        comment_id: 评论ID。
        db: 数据库会话。
        current: 当前登录用户（必须是评论作者）。
    返回:
        统一响应，data 含被删评论ID与该动态的最新评论数。
    """
    comment = db.get(PostComment, comment_id)
    if comment is None:
        raise NotFoundError("评论不存在")
    if comment.user_id != current.id:
        raise ForbiddenError("只能删除自己的评论")

    # 统计要连带删除的回复条数，便于同步 comment_count
    child_ids = list(db.scalars(select(PostComment.id).where(PostComment.parent_id == comment.id)).all())
    removed = 1 + len(child_ids)
    db.execute(delete(PostComment).where(PostComment.parent_id == comment.id))
    db.delete(comment)

    post = db.get(Post, comment.post_id)
    if post is not None:
        post.comment_count = max(0, (post.comment_count or 0) - removed)
    db.commit()
    return ok({"comment_id": comment_id, "deleted": True, "comment_count": post.comment_count if post else 0})


# ---------------------------------------------------------------- 关注关系
@router.post("/users/{user_id}/follow", summary="关注用户")
def follow_user(user_id: int, db: DbSession, current: CurrentUser) -> dict[str, Any]:
    """关注某个用户。

    参数:
        user_id: 被关注的用户ID。
        db: 数据库会话。
        current: 当前登录用户。
    返回:
        统一响应，data 为 FollowResultOut；关注自己抛 400，重复关注抛 409。
    """
    target = db.get(User, user_id)
    if target is None:
        raise NotFoundError("用户不存在")
    if target.id == current.id:
        raise BadRequestError("不能关注自己")
    exists = db.scalar(select(Follow.id).where(Follow.follower_id == current.id, Follow.following_id == target.id))
    if exists is not None:
        raise ConflictError("你已经关注过该用户了")
    db.add(Follow(follower_id=current.id, following_id=target.id))
    db.commit()
    return ok(FollowResultOut(user_id=target.id, is_following=True, follower_count=_count_followers(db, target.id)))


@router.delete("/users/{user_id}/follow", summary="取消关注")
def unfollow_user(user_id: int, db: DbSession, current: CurrentUser) -> dict[str, Any]:
    """取消关注某个用户。

    参数:
        user_id: 被取消关注的用户ID。
        db: 数据库会话。
        current: 当前登录用户。
    返回:
        统一响应，data 为 FollowResultOut。
    """
    target = db.get(User, user_id)
    if target is None:
        raise NotFoundError("用户不存在")
    follow = db.scalar(select(Follow).where(Follow.follower_id == current.id, Follow.following_id == target.id))
    if follow is None:
        raise NotFoundError("尚未关注该用户")
    db.delete(follow)
    db.commit()
    return ok(FollowResultOut(user_id=target.id, is_following=False, follower_count=_count_followers(db, target.id)))


# ---------------------------------------------------------------- 用户主页
@router.get("/users/{user_id}", summary="用户主页")
def get_user_profile(user_id: int, db: DbSession, current: OptionalUser) -> dict[str, Any]:
    """查看某个用户的主页信息。

    参数:
        user_id: 目标用户ID。
        db: 数据库会话。
        current: 可选登录用户，用于计算「我是否已关注TA」。
    返回:
        统一响应，data 为 UserProfileOut（昵称、头像、签名、等级、动态数、粉丝数、关注数、是否已关注）。
    """
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError("用户不存在")
    post_count = int(
        db.scalar(
            select(func.count()).select_from(Post).where(Post.user_id == user.id, Post.is_visible.is_(True))
        )
        or 0
    )
    following_count = int(
        db.scalar(select(func.count()).select_from(Follow).where(Follow.follower_id == user.id)) or 0
    )
    profile = UserProfileOut(
        id=user.id,
        username=user.username,
        nickname=user.nickname,
        display_name=user.nickname or user.username,
        avatar=user.avatar,
        signature=user.signature,
        level=user.level or 1,
        is_verified=bool(user.is_verified),
        is_following=_is_following(db, current.id if current else None, user.id),
        gender=user.gender or 0,
        city=user.city,
        points=user.points or 0,
        post_count=post_count,
        follower_count=_count_followers(db, user.id),
        following_count=following_count,
        created_at=user.created_at,
    )
    return ok(profile)


@router.get("/users/{user_id}/posts", summary="某个用户的动态列表")
def list_user_posts(
    user_id: int, db: DbSession, current: OptionalUser, params: PageParams = Depends(page_params)
) -> dict[str, Any]:
    """分页获取某个用户发布的可见动态（按时间倒序）。

    参数:
        user_id: 目标用户ID。
        params: 分页参数。
        db: 数据库会话。
        current: 可选登录用户，用于计算「我是否已点赞」。
    返回:
        统一响应，data 为 PageResult[PostOut]。
    """
    if db.get(User, user_id) is None:
        raise NotFoundError("用户不存在")
    stmt = (
        select(Post)
        .where(Post.user_id == user_id, Post.is_visible.is_(True))
        .order_by(Post.created_at.desc(), Post.id.desc())
    )
    rows, total = paginate(db, stmt, params)
    liked = _liked_post_ids(db, current.id if current else None, [p.id for p in rows])
    items = [_post_out(post, is_liked=post.id in liked) for post in rows]
    return ok(PageResult.build(items, total, params))


@router.get("/users/{user_id}/followers", summary="粉丝列表")
def list_followers(
    user_id: int, db: DbSession, current: OptionalUser, params: PageParams = Depends(page_params)
) -> dict[str, Any]:
    """分页获取某个用户的粉丝列表。

    参数:
        user_id: 目标用户ID。
        params: 分页参数。
        db: 数据库会话。
        current: 可选登录用户，用于标记「我是否已关注TA」。
    返回:
        统一响应，data 为 PageResult[UserCardOut]。
    """
    if db.get(User, user_id) is None:
        raise NotFoundError("用户不存在")
    stmt = (
        select(Follow)
        .where(Follow.following_id == user_id)
        .order_by(Follow.created_at.desc(), Follow.id.desc())
    )
    rows, total = paginate(db, stmt, params)
    ids = [follow.follower_id for follow in rows]
    users = {u.id: u for u in db.scalars(select(User).where(User.id.in_(ids))).all()} if ids else {}
    following = _following_ids(db, current.id if current else None, ids)
    items = [_user_card(users[uid], uid in following) for uid in ids if uid in users]
    return ok(PageResult.build(items, total, params))


@router.get("/users/{user_id}/following", summary="关注列表")
def list_following(
    user_id: int, db: DbSession, current: OptionalUser, params: PageParams = Depends(page_params)
) -> dict[str, Any]:
    """分页获取某个用户的关注列表。

    参数:
        user_id: 目标用户ID。
        params: 分页参数。
        db: 数据库会话。
        current: 可选登录用户，用于标记「我是否已关注TA」。
    返回:
        统一响应，data 为 PageResult[UserCardOut]。
    """
    if db.get(User, user_id) is None:
        raise NotFoundError("用户不存在")
    stmt = (
        select(Follow)
        .where(Follow.follower_id == user_id)
        .order_by(Follow.created_at.desc(), Follow.id.desc())
    )
    rows, total = paginate(db, stmt, params)
    ids = [follow.following_id for follow in rows]
    users = {u.id: u for u in db.scalars(select(User).where(User.id.in_(ids))).all()} if ids else {}
    following = _following_ids(db, current.id if current else None, ids)
    items = [_user_card(users[uid], uid in following) for uid in ids if uid in users]
    return ok(PageResult.build(items, total, params))


@router.get("/search/users", summary="搜索用户")
def search_users(
    db: DbSession,
    current: OptionalUser,
    keyword: str = Query(..., min_length=1, max_length=50, description="昵称或用户名关键字"),
) -> dict[str, Any]:
    """按昵称或用户名模糊搜索用户（最多返回 20 条）。

    参数:
        keyword: 搜索关键字，必填。
        db: 数据库会话。
        current: 可选登录用户，用于标记「我是否已关注TA」。
    返回:
        统一响应，data 为 UserCardOut 列表。
    """
    text = (keyword or "").strip()
    if not text:
        raise BadRequestError("搜索关键字不能为空")
    pattern = f"%{text}%"
    stmt = (
        select(User)
        .where(or_(User.username.like(pattern), User.nickname.like(pattern)))
        .order_by(User.id.desc())
        .limit(20)
    )
    users = list(db.scalars(stmt).all())
    following = _following_ids(db, current.id if current else None, [u.id for u in users])
    return ok([_user_card(user, user.id in following) for user in users])
