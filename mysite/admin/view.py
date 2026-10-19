from sqladmin import ModelView
from mysite.db.models import (UserProfile, UserStatistic, Room, RoomPlayer,Review, Game,
                              GamePlayer, GameRound,NightAction, Vote, Achievement, UserAchievement,
                              Friend, Group, Chatgroup)


class UserProfileView(ModelView, model=UserProfile):
    column_list = [UserProfile.id, UserProfile.username, UserProfile.email, UserProfile.role]
    column_details_exclude_list = [UserProfile.password]
    form_excluded_columns = [UserProfile.password]
    can_create = False


class UserStatisticView(ModelView, model=UserStatistic):
    column_list = [UserStatistic.id, UserStatistic.user_id]


class RoomView(ModelView, model=Room):
    column_list = [Room.id, Room.room_name, Room.status, Room.owner_id]


class RoomPlayerView(ModelView, model=RoomPlayer):
    column_list = [RoomPlayer.id, RoomPlayer.room_id, RoomPlayer.user_id]


class ReviewView(ModelView, model=Review):
    column_list = [Review.id, Review.user_id, Review.room_id, Review.stars]


class GameView(ModelView, model=Game):
    column_list = [
        Game.id,
        Game.room_id,
        Game.current_round,
        Game.current_phase,
        Game.winner
    ]


class GamePlayerView(ModelView, model=GamePlayer):
    column_list = [
        GamePlayer.id,
        GamePlayer.game_id,
        GamePlayer.user_id,
        GamePlayer.role,
        GamePlayer.is_alive
    ]


class GameRoundView(ModelView, model=GameRound):
    column_list = [
        GameRound.id,
        GameRound.game_id,
        GameRound.killed_player_id,
        GameRound.eliminated_player_id
    ]


class NightActionView(ModelView, model=NightAction):
    column_list = [
        NightAction.id,
        NightAction.round_id,
        NightAction.actor_id,
        NightAction.target_id,
        NightAction.action_type
    ]


class VoteView(ModelView, model=Vote):
    column_list = [
        Vote.id,
        Vote.round_id,
        Vote.voter_id,
        Vote.target_id
    ]


class AchievementView(ModelView, model=Achievement):
    column_list = [
        Achievement.id,
        Achievement.code,
        Achievement.title
    ]


class UserAchievementView(ModelView, model=UserAchievement):
    column_list = [
        UserAchievement.id,
        UserAchievement.user_id,
        UserAchievement.achievement_id,
        UserAchievement.unlocked_at
    ]


class FriendView(ModelView, model=Friend):
    column_list = [Friend.id, Friend.user_id, Friend.friend_id, Friend.created_at]

class GroupView(ModelView, model=Group):
    column_list = [Group.id, Group.member_id, Group.group_name]

class ChatgroupView(ModelView, model=Chatgroup):
    column_list = [Chatgroup.id, Chatgroup.user_id, Chatgroup.group_id, Chatgroup.text]
