class Solution {
public:
    int missingNumber(vector<int>& nums) {
        // n ditinct number

        int sum = 0;           // initializing sum to 0
        int n = nums.size(); // declare n

        // iterate whole array at once
        for (int i = 0; i < nums.size(); i++) {
            sum = sum + nums[i];
        }
 
 
        long int total = (1LL * n * (n + 1)) / 2;

        return total - sum;
    }
};