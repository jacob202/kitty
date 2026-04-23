-- 🐱 Kitty Sensei Training System - Database Schema
-- PostgreSQL Schema for gamified AI training

-- ============================================================
-- CORE TABLES
-- ============================================================

-- User profiles and progression
CREATE TABLE user_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(100),
    email VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Progression
    current_level INTEGER DEFAULT 1,
    current_xp INTEGER DEFAULT 0,
    total_xp_earned INTEGER DEFAULT 0,
    next_level_xp INTEGER DEFAULT 100,
    
    -- Title/Tier
    current_title VARCHAR(50) DEFAULT 'Kitten',
    current_tier VARCHAR(50) DEFAULT 'kitten',
    
    -- Streak tracking
    current_streak INTEGER DEFAULT 0,
    longest_streak INTEGER DEFAULT 0,
    last_training_date DATE,
    streak_started_at TIMESTAMP WITH TIME ZONE,
    
    -- Avatar customization
    avatar_style VARCHAR(50) DEFAULT 'default',
    avatar_color VARCHAR(7) DEFAULT '#FF6B9D',
    unlocked_skins JSONB DEFAULT '[]',
    
    -- Settings
    preferences JSONB DEFAULT '{
        "notifications": true,
        "sound_effects": true,
        "animation_speed": "normal",
        "theme": "default"
    }'
);

-- Stats and attributes (1-100 scale)
CREATE TABLE user_stats (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) REFERENCES user_profiles(user_id) ON DELETE CASCADE,
    
    -- Core stats
    intelligence INTEGER DEFAULT 10 CHECK (intelligence >= 1 AND intelligence <= 100),
    speed INTEGER DEFAULT 10 CHECK (speed >= 1 AND speed <= 100),
    accuracy INTEGER DEFAULT 10 CHECK (accuracy >= 1 AND accuracy <= 100),
    memory INTEGER DEFAULT 10 CHECK (memory >= 1 AND memory <= 100),
    creativity INTEGER DEFAULT 10 CHECK (creativity >= 1 AND creativity <= 100),
    
    -- Training focus (which stat to prioritize)
    training_focus VARCHAR(20) DEFAULT 'intelligence',
    
    -- Stat history for tracking progress
    stat_history JSONB DEFAULT '[]',
    
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(user_id)
);

-- Unlocked abilities
CREATE TABLE user_abilities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) REFERENCES user_profiles(user_id) ON DELETE CASCADE,
    ability_key VARCHAR(50) NOT NULL,
    ability_name VARCHAR(100) NOT NULL,
    unlocked_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    unlocked_at_level INTEGER NOT NULL,
    is_active BOOLEAN DEFAULT true,
    usage_count INTEGER DEFAULT 0,
    last_used_at TIMESTAMP WITH TIME ZONE,
    
    UNIQUE(user_id, ability_key)
);

-- Badges and achievements
CREATE TABLE badges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    badge_key VARCHAR(50) UNIQUE NOT NULL,
    badge_name VARCHAR(100) NOT NULL,
    badge_description TEXT,
    badge_icon VARCHAR(10) DEFAULT '🏆',
    badge_tier VARCHAR(20) DEFAULT 'bronze', -- bronze, silver, gold, platinum, legendary
    rarity VARCHAR(20) DEFAULT 'common', -- common, uncommon, rare, epic, legendary
    xp_reward INTEGER DEFAULT 50,
    requirements JSONB, -- JSON structure defining how to earn
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- User's earned badges
CREATE TABLE user_badges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) REFERENCES user_profiles(user_id) ON DELETE CASCADE,
    badge_key VARCHAR(50) REFERENCES badges(badge_key) ON DELETE CASCADE,
    earned_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    earned_at_level INTEGER,
    is_new BOOLEAN DEFAULT true,
    showcased BOOLEAN DEFAULT false,
    
    UNIQUE(user_id, badge_key)
);

-- ============================================================
-- TRAINING TABLES
-- ============================================================

-- Training sessions/drills completed
CREATE TABLE training_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) REFERENCES user_profiles(user_id) ON DELETE CASCADE,
    
    -- Session details
    session_type VARCHAR(50) NOT NULL, -- drill, rlhf, few_shot, correction, pattern
    skill_category VARCHAR(50), -- schematic_reading, component_id, etc.
    difficulty INTEGER DEFAULT 1 CHECK (difficulty >= 1 AND difficulty <= 5),
    
    -- Performance
    questions_total INTEGER DEFAULT 0,
    questions_correct INTEGER DEFAULT 0,
    accuracy_score DECIMAL(5,2), -- 0.00 to 1.00
    completion_time_seconds INTEGER,
    
    -- Rewards
    xp_earned INTEGER DEFAULT 0,
    stats_impacted JSONB, -- {"intelligence": 2, "accuracy": 1}
    
    -- Session data
    session_data JSONB, -- Store questions, answers, etc.
    
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    
    -- Index for querying recent sessions
    CONSTRAINT valid_accuracy CHECK (accuracy_score >= 0 AND accuracy_score <= 1)
);

-- RLHF comparisons (A/B testing responses)
CREATE TABLE rlhf_comparisons (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) REFERENCES user_profiles(user_id) ON DELETE CASCADE,
    
    query TEXT NOT NULL,
    response_a TEXT NOT NULL,
    response_b TEXT NOT NULL,
    response_c TEXT, -- Optional third response
    
    winner VARCHAR(1) NOT NULL CHECK (winner IN ('A', 'B', 'C', 'tie')),
    user_reasoning TEXT, -- Why they chose that response
    
    -- Quality metrics
    helpfulness_a INTEGER CHECK (helpfulness_a >= 1 AND helpfulness_a <= 5),
    helpfulness_b INTEGER CHECK (helpfulness_b >= 1 AND helpfulness_b <= 5),
    
    xp_earned INTEGER DEFAULT 15,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Few-shot examples gallery
CREATE TABLE few_shot_examples (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) REFERENCES user_profiles(user_id) ON DELETE CASCADE,
    
    category VARCHAR(50) NOT NULL, -- component_id, troubleshooting, etc.
    input_example TEXT NOT NULL,
    expected_output TEXT NOT NULL,
    
    -- Validation
    is_validated BOOLEAN DEFAULT false,
    validation_score DECIMAL(3,2), -- How well Kitty performs on this example
    
    -- Metadata
    tags TEXT[],
    difficulty INTEGER DEFAULT 1,
    xp_earned INTEGER DEFAULT 50,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_tested_at TIMESTAMP WITH TIME ZONE
);

-- Corrections (learning from mistakes)
CREATE TABLE corrections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) REFERENCES user_profiles(user_id) ON DELETE CASCADE,
    
    -- What went wrong
    query TEXT NOT NULL,
    kitty_response TEXT NOT NULL,
    user_correction TEXT NOT NULL,
    
    -- Categorization
    category VARCHAR(50), -- component_id, procedure, safety, theory
    severity VARCHAR(20) DEFAULT 'minor', -- minor, moderate, major, critical
    
    -- Learning tracking
    lesson_learned TEXT, -- Summary of what Kitty should remember
    related_skill VARCHAR(50),
    
    -- XP and status
    xp_earned INTEGER DEFAULT 100,
    incorporated_into_model BOOLEAN DEFAULT false,
    incorporated_at TIMESTAMP WITH TIME ZONE,
    
    -- For triggering fine-tuning
    correction_number INTEGER, -- nth correction for this user
    triggers_finetune BOOLEAN GENERATED ALWAYS AS (
        correction_number IS NOT NULL AND correction_number % 50 = 0
    ) STORED,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    resolved_at TIMESTAMP WITH TIME ZONE
);

-- Pattern recognition data
CREATE TABLE detected_patterns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) REFERENCES user_profiles(user_id) ON DELETE CASCADE,
    
    pattern_type VARCHAR(50) NOT NULL, -- behavior, repair, learning_gap, success
    pattern_name VARCHAR(100) NOT NULL,
    pattern_description TEXT,
    
    -- Detection data
    detection_data JSONB, -- Specific pattern metrics
    confidence_score DECIMAL(3,2), -- 0.00 to 1.00
    frequency_count INTEGER DEFAULT 1,
    
    -- Status
    is_active BOOLEAN DEFAULT true,
    acknowledged_by_user BOOLEAN DEFAULT false,
    
    xp_earned INTEGER DEFAULT 40,
    
    first_detected_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_occurred_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Suggested actions
    suggested_actions JSONB DEFAULT '[]'
);

-- ============================================================
-- QUEST & ACHIEVEMENT TABLES
-- ============================================================

-- Daily/weekly quests
CREATE TABLE quests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    quest_key VARCHAR(50) UNIQUE NOT NULL,
    quest_name VARCHAR(100) NOT NULL,
    quest_description TEXT,
    
    -- Requirements
    quest_type VARCHAR(20) DEFAULT 'daily', -- daily, weekly, special
    requirements JSONB NOT NULL, -- {"action": "complete_drill", "count": 3}
    
    -- Rewards
    xp_reward INTEGER DEFAULT 100,
    stat_boost VARCHAR(20), -- Optional stat to boost
    badge_reward VARCHAR(50), -- Optional badge to award
    
    difficulty INTEGER DEFAULT 1 CHECK (difficulty >= 1 AND difficulty <= 5),
    is_active BOOLEAN DEFAULT true,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- User quest progress
CREATE TABLE user_quests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) REFERENCES user_profiles(user_id) ON DELETE CASCADE,
    quest_id UUID REFERENCES quests(id) ON DELETE CASCADE,
    
    -- Progress
    progress_current INTEGER DEFAULT 0,
    progress_target INTEGER NOT NULL,
    is_completed BOOLEAN DEFAULT false,
    
    -- Timestamps
    assigned_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE, -- For daily/weekly quests
    completed_at TIMESTAMP WITH TIME ZONE,
    
    -- Rewards claimed
    xp_claimed BOOLEAN DEFAULT false,
    rewards_claimed_at TIMESTAMP WITH TIME ZONE,
    
    UNIQUE(user_id, quest_id, assigned_at)
);

-- ============================================================
-- XP & ACTIVITY TABLES
-- ============================================================

-- XP transaction log (comprehensive history)
CREATE TABLE xp_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) REFERENCES user_profiles(user_id) ON DELETE CASCADE,
    
    amount INTEGER NOT NULL, -- Can be negative for penalties
    balance_after INTEGER NOT NULL,
    
    -- Source
    source_type VARCHAR(50) NOT NULL, -- repair, correction, drill, quest, badge, etc.
    source_id UUID, -- Reference to specific activity
    source_details JSONB, -- Additional context
    
    -- Metadata
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Activity log (comprehensive user activity)
CREATE TABLE activity_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) REFERENCES user_profiles(user_id) ON DELETE CASCADE,
    
    activity_type VARCHAR(50) NOT NULL, -- login, training, level_up, ability_unlock, etc.
    activity_subtype VARCHAR(50),
    
    -- Details
    description TEXT,
    metadata JSONB,
    
    -- Related entities
    related_entity_type VARCHAR(50),
    related_entity_id UUID,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Level-up history
CREATE TABLE level_up_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) REFERENCES user_profiles(user_id) ON DELETE CASCADE,
    
    from_level INTEGER NOT NULL,
    to_level INTEGER NOT NULL,
    xp_at_level_up INTEGER NOT NULL,
    
    -- Unlocks at this level
    unlocked_abilities JSONB DEFAULT '[]',
    unlocked_features JSONB DEFAULT '[]',
    
    leveled_up_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================
-- EASTER EGGS & HIDDEN FEATURES
-- ============================================================

-- Easter egg definitions
CREATE TABLE easter_eggs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    egg_key VARCHAR(50) UNIQUE NOT NULL,
    egg_name VARCHAR(100) NOT NULL,
    
    -- Discovery
    trigger_condition VARCHAR(100) NOT NULL, -- Description of how to trigger
    trigger_pattern VARCHAR(255), -- Regex or specific pattern
    
    -- Reward
    xp_reward INTEGER DEFAULT 200,
    badge_reward VARCHAR(50),
    special_reward JSONB, -- Custom rewards
    
    -- Content
    egg_content TEXT, -- Message, animation data, etc.
    
    is_active BOOLEAN DEFAULT true,
    max_discoveries INTEGER, -- NULL = unlimited
    total_discoveries INTEGER DEFAULT 0,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- User discoveries
CREATE TABLE user_easter_eggs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) REFERENCES user_profiles(user_id) ON DELETE CASCADE,
    egg_id UUID REFERENCES easter_eggs(id) ON DELETE CASCADE,
    
    discovered_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    xp_claimed BOOLEAN DEFAULT false,
    
    UNIQUE(user_id, egg_id)
);

-- ============================================================
-- INDICES FOR PERFORMANCE
-- ============================================================

-- User profile lookups
CREATE INDEX idx_user_profiles_user_id ON user_profiles(user_id);
CREATE INDEX idx_user_profiles_level ON user_profiles(current_level);

-- Training session queries
CREATE INDEX idx_training_sessions_user_id ON training_sessions(user_id);
CREATE INDEX idx_training_sessions_type ON training_sessions(session_type);
CREATE INDEX idx_training_sessions_completed ON training_sessions(completed_at);

-- Activity tracking
CREATE INDEX idx_activity_log_user_id ON activity_log(user_id);
CREATE INDEX idx_activity_log_type ON activity_log(activity_type);
CREATE INDEX idx_activity_log_created ON activity_log(created_at);

-- XP transactions
CREATE INDEX idx_xp_transactions_user_id ON xp_transactions(user_id);
CREATE INDEX idx_xp_transactions_created ON xp_transactions(created_at);

-- Badge queries
CREATE INDEX idx_user_badges_user_id ON user_badges(user_id);
CREATE INDEX idx_user_badges_earned ON user_badges(earned_at);

-- Correction tracking
CREATE INDEX idx_corrections_user_id ON corrections(user_id);
CREATE INDEX idx_corrections_category ON corrections(category);
CREATE INDEX idx_corrections_finetune ON corrections(triggers_finetune) WHERE triggers_finetune = true;

-- ============================================================
-- SEED DATA
-- ============================================================

-- Insert default badges
INSERT INTO badges (badge_key, badge_name, badge_description, badge_icon, badge_tier, rarity, xp_reward) VALUES
-- Original badges from sensei_v2
('OSCILLOSCOPE_EYE', 'Oscilloscope Eye', 'Corrected a hallucination', '🎛️', 'silver', 'uncommon', 100),
('SCHEMATIC_SAGE', 'Schematic Sage', 'Perfect 5-turn interaction', '📚', 'gold', 'rare', 200),
('GOLDEN_EAR', 'Golden Ear', 'Remembered favorite model', '🎧', 'silver', 'uncommon', 100),
('CIRCUIT_BENDER', 'Circuit Bender', 'Triggered reasoning mode', '⚡', 'bronze', 'common', 50),
('SENSEI_APPRENTICE', 'Sensei Apprentice', 'Accumulated 500 XP', '🥋', 'bronze', 'common', 100),

-- Training badges
('CORRECTION_COLLECTOR', 'Correction Collector', 'Logged 20 corrections', '✏️', 'silver', 'uncommon', 150),
('DRILL_MASTER', 'Drill Master', 'Completed 50 training drills', '🎯', 'gold', 'rare', 300),
('PATTERN_SEEKER', 'Pattern Seeker', 'Detected 10 user patterns', '🔮', 'silver', 'uncommon', 200),
('HUMBLE_STUDENT', 'Humble Student', 'Learned from 20 corrections', '📖', 'bronze', 'common', 100),
('TEACHER_PET', 'Teacher Pet', 'Achieved 90% drill accuracy', '🍎', 'gold', 'rare', 250),

-- Skill-specific badges
('SCHEMATIC_SAGE_MASTER', 'Schematic Master', 'Complete all schematic drills', '📐', 'platinum', 'epic', 500),
('COMPONENT_EXPERT', 'Component Expert', '100 correct component IDs', '🔬', 'gold', 'rare', 300),
('CIRCUIT_WHISPERER', 'Circuit Whisperer', '50 successful repairs', '🔧', 'platinum', 'epic', 500),
('SAFETY_FIRST', 'Safety First', 'Perfect safety protocol score', '⚡', 'gold', 'rare', 200),
('OHMS_LAWYER', 'Ohm Lawyer', 'Master all theory drills', '⚖️', 'gold', 'rare', 300),
('DATASHEET_PROPHET', 'Datasheet Prophet', 'Extract data from 50 datasheets', '📜', 'silver', 'uncommon', 200),

-- Engagement badges
('DEDICATED_TRAINER', 'Dedicated Trainer', '7-day training streak', '🔥', 'bronze', 'common', 100),
('COMMITTED_COACH', 'Committed Coach', '30-day training streak', '💪', 'silver', 'uncommon', 300),
('LEGENDARY_MENTOR', 'Legendary Mentor', '100-day training streak', '⭐', 'gold', 'rare', 1000),
('NIGHT_OWL', 'Night Owl', 'Train after midnight', '🦉', 'bronze', 'common', 50),
('EARLY_BIRD', 'Early Bird', 'Train before 6am', '🐦', 'bronze', 'common', 50),

-- Social badges
('KNOWLEDGE_SHARER', 'Knowledge Sharer', 'Help another user', '🤝', 'silver', 'uncommon', 150),
('COMMUNITY_SENSEI', 'Community Sensei', 'Share custom skill', '🌟', 'gold', 'rare', 500),

-- Rare/Shiny badges
('PERFECT_SCORE', 'Perfect Score', '100% on expert drill', '💎', 'platinum', 'epic', 1000),
('EASTER_EGG_HUNTER', 'Easter Egg Hunter', 'Find hidden feature', '🥚', 'silver', 'uncommon', 200),
('SPEED_DEMON', 'Speed Demon', 'Complete drill in <30s', '🏃', 'gold', 'rare', 300),

-- Ultimate badge
('SENSEI_MASTER', 'Sensei Master', 'Reach Level 50', '👑', 'legendary', 'legendary', 10000);

-- Insert default quests
INSERT INTO quests (quest_key, quest_name, quest_description, quest_type, requirements, xp_reward, difficulty) VALUES
('warm_up', 'Morning Stretch', 'Complete 1 training drill', 'daily', '{"action": "complete_drill", "count": 1}', 25, 1),
('correction_session', 'Humble Beginnings', 'Review and log a correction', 'daily', '{"action": "log_correction", "count": 1}', 50, 2),
('deep_dive', 'Deep Dive', 'Spend 15 minutes in RLHF training', 'daily', '{"action": "rlhf_time", "minutes": 15}', 75, 3),
('pattern_spotter', 'Pattern Detective', 'Identify and document a pattern', 'daily', '{"action": "detect_pattern", "count": 1}', 40, 2),
('skill_showcase', 'Skill Showcase', 'Use a newly unlocked ability', 'daily', '{"action": "use_ability", "count": 1}', 60, 2),
('marathon', 'Training Marathon', 'Complete 5 drills with 80%+ accuracy', 'daily', '{"action": "complete_drills", "count": 5, "accuracy": 0.8}', 150, 4),
('masterclass', 'Masterclass', 'Help another user with their repair', 'daily', '{"action": "help_user", "count": 1}', 100, 3),
('weekly_warrior', 'Weekly Warrior', 'Complete 20 training sessions this week', 'weekly', '{"action": "complete_sessions", "count": 20}', 500, 3);

-- Insert easter eggs
INSERT INTO easter_eggs (egg_key, egg_name, trigger_condition, trigger_pattern, xp_reward, egg_content) VALUES
('konami_code', 'Konami Kitty', 'Enter Konami code (↑↑↓↓←→←→BA)', 'up up down down left right left right b a', 200, 'Retro 8-bit Kitty theme unlocked!'),
('midnight_meow', 'Midnight Meow', 'Interact at exactly 3:33 AM', NULL, 200, 'The spirits are pleased... Ghost Kitty appears with wisdom!'),
('pet_the_kitty', 'Pet the Kitty', 'Click avatar 10 times rapidly', NULL, 50, 'Prrrrrr... Kitty is happy!'),
('sudo_train', 'Root Access', 'Type sudo train kitty', 'sudo train kitty', 300, 'Root access granted! Admin training mode unlocked.'),
('cheshire_cat', 'Cheshire Wisdom', 'Ask Who are you really?', 'who are you really', 150, 'We are all mad here...');

-- ============================================================
-- FUNCTIONS & TRIGGERS
-- ============================================================

-- Function to update timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply to tables
CREATE TRIGGER update_user_profiles_updated_at BEFORE UPDATE ON user_profiles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_stats_updated_at BEFORE UPDATE ON user_stats
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Function to handle XP transactions and level ups
CREATE OR REPLACE FUNCTION process_xp_transaction()
RETURNS TRIGGER AS $$
DECLARE
    current_level INTEGER;
    current_xp INTEGER;
    new_level INTEGER;
    next_level_threshold INTEGER;
BEGIN
    -- Get current user state
    SELECT current_level, current_xp INTO current_level, current_xp
    FROM user_profiles WHERE user_id = NEW.user_id;
    
    -- Calculate new XP
    current_xp := current_xp + NEW.amount;
    
    -- Check for level up using XP table
    SELECT level, xp_required INTO new_level, next_level_threshold
    FROM (VALUES 
        (1, 0), (2, 100), (3, 250), (4, 450), (5, 700),
        (6, 1000), (7, 1400), (8, 1900), (9, 2500), (10, 3200),
        (11, 4000), (12, 5000), (13, 6200), (14, 7600), (15, 9200),
        (16, 11000), (17, 13000), (18, 15200), (19, 17600), (20, 20200),
        (21, 23000), (22, 26200), (23, 29800), (24, 33800), (25, 38200),
        (26, 43000), (27, 48400), (28, 54400), (29, 61000), (30, 68400),
        (31, 76600), (32, 85600), (33, 95400), (34, 106000), (35, 117400),
        (36, 129600), (37, 142600), (38, 156400), (39, 171000), (40, 186400),
        (41, 202600), (42, 219600), (43, 237400), (44, 256000), (45, 275400),
        (46, 295600), (47, 316600), (48, 338400), (49, 361000), (50, 384400)
    ) AS levels(level, xp_required)
    WHERE xp_required <= current_xp
    ORDER BY level DESC
    LIMIT 1;
    
    -- Update user profile
    UPDATE user_profiles SET
        current_xp = current_xp,
        total_xp_earned = total_xp_earned + NEW.amount,
        next_level_xp = next_level_threshold,
        current_level = new_level,
        updated_at = NOW()
    WHERE user_id = NEW.user_id;
    
    -- If leveled up, record it
    IF new_level > current_level THEN
        INSERT INTO level_up_history (user_id, from_level, to_level, xp_at_level_up)
        VALUES (NEW.user_id, current_level, new_level, current_xp);
        
        -- TODO: Trigger ability unlocks, notifications, etc.
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for XP processing
CREATE TRIGGER after_xp_transaction_insert
    AFTER INSERT ON xp_transactions
    FOR EACH ROW
    EXECUTE FUNCTION process_xp_transaction();

-- Function to update streak
CREATE OR REPLACE FUNCTION update_training_streak()
RETURNS TRIGGER AS $$
DECLARE
    last_date DATE;
    current_streak INTEGER;
BEGIN
    SELECT last_training_date, current_streak INTO last_date, current_streak
    FROM user_profiles WHERE user_id = NEW.user_id;
    
    -- Check if this is a new day
    IF last_date IS NULL OR last_date < CURRENT_DATE THEN
        IF last_date = CURRENT_DATE - 1 THEN
            -- Consecutive day
            UPDATE user_profiles SET
                current_streak = current_streak + 1,
                longest_streak = GREATEST(longest_streak, current_streak + 1),
                last_training_date = CURRENT_DATE
            WHERE user_id = NEW.user_id;
        ELSE
            -- Streak broken
            UPDATE user_profiles SET
                current_streak = 1,
                last_training_date = CURRENT_DATE,
                streak_started_at = NOW()
            WHERE user_id = NEW.user_id;
        END IF;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for streak updates
CREATE TRIGGER after_training_session_insert
    AFTER INSERT ON training_sessions
    FOR EACH ROW
    EXECUTE FUNCTION update_training_streak();
