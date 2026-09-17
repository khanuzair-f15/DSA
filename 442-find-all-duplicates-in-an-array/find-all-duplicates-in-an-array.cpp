class Solution {
public:
    vector<int> findDuplicates(vector<int>& nums) {

        unordered_set<int> s;
        vector<int> v;

        for (int i : nums) {

            if (s.count(i)) {
                v.push_back(i);
            }else{
                s.insert(i);
            }
        }
        return v;
    }
};