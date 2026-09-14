import { createClient } from 'https://cdn.jsdelivr.net/npm/@supabase/supabase-js/+esm';

const supabaseUrl = window.SUPABASE_URL || '';
const supabaseAnonKey = window.SUPABASE_KEY || '';

export const supabase = createClient(supabaseUrl, supabaseAnonKey);
