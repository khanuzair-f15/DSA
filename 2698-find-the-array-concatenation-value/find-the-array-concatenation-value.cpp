class Solution {
public:
    long long findTheArrayConcVal(vector<int>& nums) {
        int i = 0;
        int j = nums.size() - 1;
        long long ans = 0;
        while (i < j) {
            string a = to_string(nums[i]);
            string b = to_string(nums[j]);

            string combined = a + b;
            ans = ans + stoll(combined);
            i++;
            j--;
        }
        if (i == j) {
            ans = ans + nums[i];
        }
        return ans;
    }
};