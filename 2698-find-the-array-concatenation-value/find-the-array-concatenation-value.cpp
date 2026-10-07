class Solution {
public:
    long long countDigit(int n) {
        long long count = 1;
        while (n != 0) {
            n = n / 10;
            count = count * 10;
        }
        return count;
    }
    long long findTheArrayConcVal(vector<int>& nums) {
        int i = 0;
        int j = nums.size() - 1;
        long long sum = 0;
        while (i < j) {
            sum += nums[i] * countDigit(nums[j]) + nums[j];
            cout << countDigit(nums[j]) << " " << sum << endl;
            i++;
            j--;
        }
        // 74 + 522
        if (nums.size() % 2 != 0) {
            sum += nums[nums.size() / 2];
        }
        return sum;
    }
};