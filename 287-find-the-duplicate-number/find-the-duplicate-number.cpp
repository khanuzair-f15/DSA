class Solution {
public:
    int findDuplicate(vector<int>& nums) {
        // the code below uses unsorted set means this code has significantly
        // high space requierment
        /*
        unordered_set<int> s;

        for (int i = 0; i < nums.size(); i++) {
            if (s.count(nums[i])) {
                return nums[i];
            }
            s.insert(nums[i]);
        }
        return 0;
        ☻*/
        // now in order to reduce space complexity also we will use floyds cycle
        int slow = nums[0];
        int fast = nums[0];
        do {
            slow = nums[slow];
            fast = nums[nums[fast]];
        } while (slow != fast);

        // find entrance of floyds cycle
        slow = nums[0];
        while (slow != fast) {
            slow = nums[slow];
            fast = nums[fast];
        }
        return slow;
    }
};