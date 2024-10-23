# src/infrastructure/persistence.py
from datetime import datetime
import logging
from typing import List, Optional
from uuid import UUID
import boto3
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError

from ..domain.models import User, RefreshToken, UserRole, UserStatus
from ..domain.repositories import UserRepository, RefreshTokenRepository

logger = logging.getLogger(__name__)

class DynamoDBUserRepository(UserRepository):
    def __init__(self, table_name: str, dynamodb=None):
        self.table_name = table_name
        self.dynamodb = dynamodb or boto3.resource('dynamodb')
        self.table = self.dynamodb.Table(table_name)

    async def save(self, user: User) -> User:
        try:
            item = {
                'id': str(user.id),
                'username': user.username,
                'email': user.email,
                'password_hash': user.password_hash,
                'role': user.role.value,
                'status': user.status.value,
                'created_at': user.created_at.isoformat(),
                'updated_at': user.updated_at.isoformat(),
                'last_login': user.last_login.isoformat() if user.last_login else None,
                'entity_type': 'user'  # For filtering in queries
            }
            
            self.table.put_item(
                Item=item,
                ConditionExpression='attribute_not_exists(id) OR id = :id',
                ExpressionAttributeValues={':id': str(user.id)}
            )
            return user
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                raise ValueError(f"User with id {user.id} already exists")
            logger.error(f"Error saving user: {e}")
            raise

    async def get_by_id(self, user_id: UUID) -> Optional[User]:
        try:
            response = self.table.get_item(
                Key={'id': str(user_id)}
            )
            item = response.get('Item')
            return self._deserialize_user(item) if item else None
        except ClientError as e:
            logger.error(f"Error getting user by id: {e}")
            raise

    async def get_by_email(self, email: str) -> Optional[User]:
        try:
            response = self.table.query(
                IndexName='email-index',
                KeyConditionExpression=Key('email').eq(email),
                FilterExpression=Attr('entity_type').eq('user')
            )
            items = response.get('Items', [])
            return self._deserialize_user(items[0]) if items else None
        except ClientError as e:
            logger.error(f"Error getting user by email: {e}")
            raise

    async def get_by_username(self, username: str) -> Optional[User]:
        try:
            response = self.table.query(
                IndexName='username-index',
                KeyConditionExpression=Key('username').eq(username),
                FilterExpression=Attr('entity_type').eq('user')
            )
            items = response.get('Items', [])
            return self._deserialize_user(items[0]) if items else None
        except ClientError as e:
            logger.error(f"Error getting user by username: {e}")
            raise

    async def update(self, user: User) -> User:
        update_expr = ['SET']
        expr_names = {}
        expr_values = {}
        
        fields = {
            '#username': ('username', user.username),
            '#email': ('email', user.email),
            '#ph': ('password_hash', user.password_hash),
            '#role': ('role', user.role.value),
            '#status': ('status', user.status.value),
            '#ua': ('updated_at', user.updated_at.isoformat())
        }
        
        if user.last_login:
            fields['#ll'] = ('last_login', user.last_login.isoformat())
        
        for key, (attr_name, value) in fields.items():
            expr_names[key] = attr_name
            expr_values[f':{attr_name}'] = value
            update_expr.append(f'{key} = :{attr_name},')
        
        update_expr[-1] = update_expr[-1].rstrip(',')
        
        try:
            self.table.update_item(
                Key={'id': str(user.id)},
                UpdateExpression=' '.join(update_expr),
                ExpressionAttributeNames=expr_names,
                ExpressionAttributeValues=expr_values,
                ConditionExpression='attribute_exists(id)'
            )
            return user
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                raise ValueError(f"User with id {user.id} does not exist")
            logger.error(f"Error updating user: {e}")
            raise

    async def delete(self, user_id: UUID) -> bool:
        try:
            self.table.delete_item(
                Key={'id': str(user_id)},
                ConditionExpression='attribute_exists(id)'
            )
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                return False
            logger.error(f"Error deleting user: {e}")
            raise

    def _deserialize_user(self, item: dict) -> Optional[User]:
        if not item:
            return None
        
        return User(
            id=UUID(item['id']),
            username=item['username'],
            email=item['email'],
            password_hash=item['password_hash'],
            role=UserRole(item['role']),
            status=UserStatus(item['status']),
            created_at=datetime.fromisoformat(item['created_at']),
            updated_at=datetime.fromisoformat(item['updated_at']),
            last_login=datetime.fromisoformat(item['last_login']) if item.get('last_login') else None
        )

class DynamoDBRefreshTokenRepository(RefreshTokenRepository):
    def __init__(self, table_name: str, dynamodb=None):
        self.table_name = table_name
        self.dynamodb = dynamodb or boto3.resource('dynamodb')
        self.table = self.dynamodb.Table(table_name)

    async def save(self, refresh_token: RefreshToken) -> RefreshToken:
        try:
            item = {
                'id': str(refresh_token.id),
                'user_id': str(refresh_token.user_id),
                'token': refresh_token.token,
                'expires_at': refresh_token.expires_at.isoformat(),
                'created_at': refresh_token.created_at.isoformat(),
                'revoked_at': refresh_token.revoked_at.isoformat() if refresh_token.revoked_at else None,
                'entity_type': 'refresh_token'
            }
            
            self.table.put_item(
                Item=item,
                ConditionExpression='attribute_not_exists(id) OR id = :id',
                ExpressionAttributeValues={':id': str(refresh_token.id)}
            )
            return refresh_token
        except ClientError as e:
            logger.error(f"Error saving refresh token: {e}")
            raise

    async def get_by_token(self, token: str) -> Optional[RefreshToken]:
        try:
            response = self.table.query(
                IndexName='token-index',
                KeyConditionExpression=Key('token').eq(token),
                FilterExpression=Attr('entity_type').eq('refresh_token')
            )
            items = response.get('Items', [])
            return self._deserialize_refresh_token(items[0]) if items else None
        except ClientError as e:
            logger.error(f"Error getting refresh token: {e}")
            raise

    async def get_active_by_user_id(self, user_id: UUID) -> List[RefreshToken]:
        try:
            response = self.table.query(
                IndexName='user-id-index',
                KeyConditionExpression=Key('user_id').eq(str(user_id)),
                FilterExpression=
                    Attr('entity_type').eq('refresh_token') & 
                    Attr('revoked_at').not_exists() & 
                    Attr('expires_at').gt(datetime.utcnow().isoformat())
            )
            
            return [
                self._deserialize_refresh_token(item)
                for item in response.get('Items', [])
            ]
        except ClientError as e:
            logger.error(f"Error getting active refresh tokens: {e}")
            raise

    async def revoke_all_for_user(self, user_id: UUID) -> None:
        try:
            active_tokens = await self.get_active_by_user_id(user_id)
            revoke_time = datetime.utcnow()
            
            with self.table.batch_writer() as batch:
                for token in active_tokens:
                    token.revoke()
                    item = {
                        'id': str(token.id),
                        'user_id': str(token.user_id),
                        'token': token.token,
                        'expires_at': token.expires_at.isoformat(),
                        'created_at': token.created_at.isoformat(),
                        'revoked_at': revoke_time.isoformat(),
                        'entity_type': 'refresh_token'
                    }
                    batch.put_item(Item=item)
        except ClientError as e:
            logger.error(f"Error revoking refresh tokens: {e}")
            raise

    async def delete_expired(self) -> int:
        try:
            current_time = datetime.utcnow().isoformat()
            response = self.table.scan(
                FilterExpression=
                    Attr('entity_type').eq('refresh_token') & 
                    Attr('expires_at').lt(current_time)
            )
            
            count = 0
            with self.table.batch_writer() as batch:
                for item in response.get('Items', []):
                    batch.delete_item(Key={'id': item['id']})
                    count += 1
            
            return count
        except ClientError as e:
            logger.error(f"Error deleting expired tokens: {e}")
            raise

    def _deserialize_refresh_token(self, item: dict) -> Optional[RefreshToken]:
        if not item:
            return None
            
        return RefreshToken(
            id=UUID(item['id']),
            user_id=UUID(item['user_id']),
            token=item['token'],
            expires_at=datetime.fromisoformat(item['expires_at']),
            created_at=datetime.fromisoformat(item['created_at']),
            revoked_at=datetime.fromisoformat(item['revoked_at']) if item.get('revoked_at') else None
        )