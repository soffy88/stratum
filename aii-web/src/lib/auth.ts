export interface UserPublic {
  user_id: string;
  email: string;
  username: string;
  email_verified: boolean;
  created_at: string;
}

export interface LoginResponse {
  access_token: string;
  expires_in: number;
  user: UserPublic;
}

export interface RegisterResponse {
  user_id: string;
  email: string;
  username: string;
  verify_email_sent: boolean;
}
