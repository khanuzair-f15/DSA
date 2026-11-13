class Solution {
public:
    bool prime(int n) {
        if (n == 0 || n == 1) {
            return false;
        }
        for (int i = 2; i * i <= n; i++) {
            if (n % i == 0) {
                return false;
            }
        }
        return true;
    }

    bool checkPrimeFrequency(vector<int>& nums) {
        map<int, int> mp;
        for (auto i : nums) {
            mp[i]++;
        }
        for (auto i : mp) {
            if (prime(i.second)) {
                return true;
            }
        }
        return false;
    }
};