import os, sys
sys.path.insert(0, os.path.join(os.getcwd(), 'backend'))
from database.models import User, Profile

print('FKs', User.supabase_id.property.columns[0].foreign_keys)
print('user.profile', User.profile.property)
print('profile.user', Profile.user.property)

# check primaryjoin expression
print('profile.user primaryjoin ->', Profile.user.property.primaryjoin)
