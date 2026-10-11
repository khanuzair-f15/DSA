class Solution {
public:
    int pivotIndex(vector<int>& nums) {
        // 1 7 3 6 5 6
        // 1 8 11 17 22 28
        int sum = 0;

        vector<int> v;
        for (int i = 0; i < nums.size(); i++) {
            sum += nums[i];
            v.push_back(sum);
            cout << sum << " ";
        }
        // 2 1 -1
        // 2 3 2
        if (nums[0] == v[nums.size() - 1]) {
            return 0;
        }

        int index = -1;

        for (int i = 1; i < v.size(); i++) {
            if (v[i - 1] == v[v.size() - 1] - v[i]) {
                index = i;
                return index;
            }
        }

        return index;
    }
};