from fraud_platform.eda import profile


def test_profile_counts_exact_duplicates_and_missing_values(tmp_path):
    source = tmp_path / "paysim.csv"
    source.write_text(
        "step,type,amount,nameOrig,oldbalanceOrg,newbalanceOrig,nameDest,"
        "oldbalanceDest,newbalanceDest,isFraud,isFlaggedFraud\n"
        "1,PAYMENT,10,C1,50,40,M1,0,0,0,0\n"
        "1,PAYMENT,10,C1,50,40,M1,0,0,0,0\n"
        "2,TRANSFER,,C2,20,0,C3,0,20,1,0\n",
        encoding="utf-8",
    )

    result = profile(source)

    assert result["rows"] == 3
    assert result["exact_duplicates"] == 1
    assert result["missing"]["amount"] == 1
    assert result["fraud_rate"] == 1 / 3
    assert result["fraud_by_type"] == {"TRANSFER": 1}
    assert result["by_step"] == {1: 2, 2: 1}
